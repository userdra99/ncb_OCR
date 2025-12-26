"""Gmail Watch + Pub/Sub listener worker for real-time email notifications."""

import asyncio
import base64
import json
from datetime import datetime, timedelta
from typing import Optional

from google.cloud import pubsub_v1
from google.oauth2.credentials import Credentials

from src.config.settings import settings
from src.services.email_service import EmailService
from src.services.queue_service import QueueService
from src.utils.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


class EmailWatchListener:
    """
    Gmail Watch + Pub/Sub listener worker.
    
    Replaces polling with push notifications from Gmail API.
    Near-zero quota usage - only makes API calls when emails actually arrive.
    """

    def __init__(self) -> None:
        """Initialize worker."""
        self.email_service = EmailService()
        self.queue_service = QueueService()
        self.running = False
        self.watch_expiration: Optional[datetime] = None
        self.event_loop: Optional[asyncio.AbstractEventLoop] = None

        # Pub/Sub configuration
        self.project_id = settings.google_cloud.project_id
        self.topic_name = settings.gmail.pubsub_topic_name
        self.subscription_name = settings.gmail.pubsub_subscription_name

        logger.info(
            "Email watch listener initialized",
            project=self.project_id,
            topic=self.topic_name,
            subscription=self.subscription_name
        )

    async def run(self) -> None:
        """Main worker loop."""
        self.running = True
        # Store reference to the current event loop for Pub/Sub callback
        self.event_loop = asyncio.get_running_loop()

        await self.queue_service.connect()
        await self.email_service.connect_redis()

        logger.info("Email watch listener started")

        try:
            # Set up Gmail watch (push notifications)
            await self._setup_gmail_watch()

            # Listen to Pub/Sub messages
            await self._listen_to_pubsub()

        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received, shutting down...")
        except Exception as e:
            logger.error("Watch listener error", error=str(e))
            raise
        finally:
            await self._cleanup()

    async def _setup_gmail_watch(self) -> None:
        """
        Set up Gmail push notifications using watch API.
        
        This tells Gmail to send push notifications to our Pub/Sub topic
        whenever new emails arrive that match our query.
        """
        try:
            # Build watch request
            watch_request = {
                "labelIds": ["INBOX"],
                "labelFilterAction": "include",
                "topicName": f"projects/{self.project_id}/topics/{self.topic_name}"
            }

            # Execute watch request (non-blocking)
            result = await asyncio.to_thread(
                lambda: self.email_service.service.users()
                .watch(userId="me", body=watch_request)
                .execute()
            )

            # Calculate expiration (Gmail watch expires after 7 days)
            history_id = result.get("historyId")
            expiration_ms = int(result.get("expiration", 0))
            self.watch_expiration = datetime.fromtimestamp(expiration_ms / 1000)

            logger.info(
                "Gmail watch enabled",
                history_id=history_id,
                expires_at=self.watch_expiration.isoformat(),
                topic=f"projects/{self.project_id}/topics/{self.topic_name}"
            )

        except Exception as e:
            logger.error("Failed to setup Gmail watch", error=str(e))
            raise

    async def _renew_watch_if_needed(self) -> None:
        """Renew Gmail watch before expiration."""
        if not self.watch_expiration:
            return

        # Renew 1 day before expiration
        time_until_expiration = self.watch_expiration - datetime.now()
        if time_until_expiration < timedelta(days=1):
            logger.info("Renewing Gmail watch (expiring soon)")
            await self._setup_gmail_watch()

    async def _listen_to_pubsub(self) -> None:
        """
        Listen to Pub/Sub subscription for Gmail notifications.

        This is a long-running async operation that receives push
        notifications from Gmail when new emails arrive.

        Uses existing OAuth credentials (no service account needed).
        """
        # Use OAuth credentials from email service (reuse existing auth)
        from google.oauth2.credentials import Credentials

        # Load OAuth credentials from gmail_token.json
        creds = Credentials.from_authorized_user_file(
            str(settings.gmail.token_path),
            scopes=[
                "https://www.googleapis.com/auth/gmail.readonly",
                "https://www.googleapis.com/auth/gmail.modify",
                "https://www.googleapis.com/auth/gmail.labels",
                "https://www.googleapis.com/auth/drive.file",
                "https://www.googleapis.com/auth/pubsub",
            ]
        )

        # Create Pub/Sub subscriber with OAuth credentials
        subscriber = pubsub_v1.SubscriberClient(credentials=creds)
        subscription_path = subscriber.subscription_path(
            self.project_id,
            self.subscription_name
        )

        logger.info("Listening to Pub/Sub subscription (OAuth)", subscription=subscription_path)

        def callback(message):
            """
            Handle incoming Pub/Sub message.

            This callback runs in the Pub/Sub subscriber thread, not in the
            async event loop. We use run_coroutine_threadsafe to schedule
            the async processing on the main event loop.
            """
            try:
                # Decode message data
                data = json.loads(message.data.decode("utf-8"))
                email_address = data.get("emailAddress")
                history_id = data.get("historyId")

                logger.info(
                    "Received Gmail notification",
                    email=email_address,
                    history_id=history_id
                )

                # Schedule async processing on the main event loop
                # (callback runs in Pub/Sub thread, not async context)
                if self.event_loop:
                    asyncio.run_coroutine_threadsafe(
                        self._process_notification(history_id),
                        self.event_loop
                    )
                else:
                    logger.error("Event loop not available, cannot process notification")
                    message.nack()
                    return

                # Acknowledge message
                message.ack()

            except Exception as e:
                logger.error("Failed to process Pub/Sub message", error=str(e))
                message.nack()  # Requeue for retry

        # Subscribe to messages (blocking call in thread pool)
        streaming_pull_future = subscriber.subscribe(
            subscription_path,
            callback=callback
        )

        try:
            # Run in thread pool to avoid blocking
            await asyncio.to_thread(lambda: streaming_pull_future.result())
        except TimeoutError:
            streaming_pull_future.cancel()
            streaming_pull_future.result()  # Block until cancelled
        except Exception as e:
            logger.error("Pub/Sub subscription error", error=str(e))
            streaming_pull_future.cancel()
            raise

    async def _process_notification(self, history_id: str) -> None:
        """
        Process Gmail notification.
        
        When Gmail sends a notification, we poll the inbox to get
        new emails. This uses the batch request implementation to
        efficiently fetch metadata.
        
        Args:
            history_id: Gmail history ID from notification
        """
        try:
            # Renew watch if needed
            await self._renew_watch_if_needed()

            # Poll inbox for new emails (uses batch requests)
            emails = await self.email_service.poll_inbox()

            if not emails:
                logger.debug("No new emails found", history_id=history_id)
                return

            logger.info(
                "Processing emails from notification",
                count=len(emails),
                history_id=history_id
            )

            # Process each email (download attachments, create jobs)
            for email in emails:
                try:
                    await self._process_email(email)
                except Exception as e:
                    logger.error(
                        "Failed to process email",
                        email_id=email.message_id,
                        error=str(e)
                    )

        except Exception as e:
            logger.error("Failed to process notification", history_id=history_id, error=str(e))

    async def _process_email(self, email) -> None:
        """
        Process single email (same logic as email_poller).
        
        This is imported from the original email poller worker.
        """
        from src.workers.email_poller import EmailPollerWorker
        
        # Use email poller's processing logic
        poller = EmailPollerWorker()
        poller.email_service = self.email_service
        poller.queue_service = self.queue_service
        poller.temp_dir = settings.storage.temp_storage_path
        
        await poller._process_email(email)

    async def _cleanup(self) -> None:
        """Cleanup resources."""
        logger.info("Cleaning up email watch listener...")
        
        # Stop Gmail watch
        try:
            await asyncio.to_thread(
                lambda: self.email_service.service.users()
                .stop(userId="me")
                .execute()
            )
            logger.info("Gmail watch stopped")
        except Exception as e:
            logger.warning("Failed to stop Gmail watch", error=str(e))

        await self.email_service.disconnect_redis()
        await self.queue_service.disconnect()
        logger.info("Email watch listener stopped")

    async def stop(self) -> None:
        """Stop worker gracefully."""
        logger.info("Stopping email watch listener...")
        self.running = False


async def main():
    """Entry point for email watch listener worker."""
    worker = EmailWatchListener()
    try:
        await worker.run()
    except KeyboardInterrupt:
        await worker.stop()


if __name__ == "__main__":
    asyncio.run(main())
