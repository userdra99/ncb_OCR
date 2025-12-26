"""OCR processor worker for text extraction."""

import asyncio
import random
from pathlib import Path
from typing import Optional

from src.config.settings import settings
from src.models.job import JobStatus
from src.models.extraction import EmailExtractionResult, ExtractionResult
from src.models.claim import ExtractedClaim
from src.services.drive_service import DriveService
from src.services.ocr_service import OCRService
from src.services.queue_service import QueueService
from src.services.sheets_service import SheetsService
from src.services.data_fusion import DataFusionEngine, FusionConfig, FusedExtractionResult
from src.utils.field_validators import FieldValidator
from src.utils.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


class OCRProcessorWorker:
    """
    OCR processor worker.

    Processes images through OCR pipeline:
    - Extracts text and structured data
    - Calculates confidence scores
    - Routes based on confidence threshold
    - Logs to Sheets
    - Archives to Drive
    """

    def __init__(self) -> None:
        """Initialize worker."""
        self.ocr_service = OCRService()
        self.queue_service = QueueService()
        self.sheets_service = SheetsService()
        self.drive_service = DriveService()

        # Phase 3: Data fusion engine
        self.fusion_engine = DataFusionEngine(
            FusionConfig(
                exact_match_boost=settings.data_fusion.exact_match_boost,
                fuzzy_match_boost=settings.data_fusion.fuzzy_match_boost,
                prefer_ocr_fields=settings.data_fusion.prefer_ocr_fields,
                prefer_email_fields=settings.data_fusion.prefer_email_fields,
            )
        )

        self.running = False
        logger.info("OCR processor worker initialized", fusion_enabled=settings.data_fusion.enable_fusion)

    async def run(self) -> None:
        """Main worker loop."""
        self.running = True
        await self.queue_service.connect()

        logger.info("OCR processor worker started")

        while self.running:
            try:
                # Dequeue job from OCR queue
                job = await self.queue_service.dequeue_job(
                    settings.redis.ocr_queue, timeout=1
                )

                if job:
                    await self._process_job(job)

            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received, shutting down...")
                break
            except Exception as e:
                logger.error("Processing error", error=str(e))
                await asyncio.sleep(1)

        await self.queue_service.disconnect()
        logger.info("OCR processor worker stopped")

    async def stop(self) -> None:
        """Stop worker gracefully."""
        logger.info("Stopping OCR processor worker...")
        self.running = False

    async def _process_job(self, job) -> None:
        """
        Process single job through OCR pipeline.

        Steps:
        1. Load image
        2. Run OCR extraction
        3. Structure data
        4. Calculate confidence
        5. Route based on confidence
        6. Log to Sheets
        7. Archive to Drive
        """
        logger.info(
            "Processing job",
            job_id=job.id,
            email_id=job.email_id,
            filename=job.attachment_filename,
        )

        try:
            # Update status to processing
            await self.queue_service.update_job_status(job.id, JobStatus.PROCESSING)

            # Run OCR extraction
            image_path = Path(job.attachment_path)
            extraction_result = await self.ocr_service.extract_structured_data(image_path)

            # Phase 3: Fuse email and OCR extractions
            if settings.data_fusion.enable_fusion:
                try:
                    # Get email extraction from job metadata
                    email_extraction = self._get_email_extraction_from_job(job)

                    # Prepare OCR extraction data
                    ocr_extraction_dict = {
                        "member_id": extraction_result.claim.member_id,
                        "member_name": extraction_result.claim.member_name,
                        "provider_name": extraction_result.claim.provider_name,
                        "service_date": extraction_result.claim.service_date,
                        "receipt_number": extraction_result.claim.receipt_number,
                        "total_amount": extraction_result.claim.total_amount,
                        "gst_sst_amount": (
                            extraction_result.claim.gst_amount
                            if extraction_result.claim.gst_amount
                            else extraction_result.claim.sst_amount
                        ),
                        "provider_address": extraction_result.claim.provider_address,
                        "policy_number": extraction_result.claim.policy_number,
                        "field_confidences": extraction_result.field_confidences,
                    }

                    # Fuse extractions
                    fused_result = await self.fusion_engine.fuse_extractions(
                        email_extraction, extraction_result
                    )

                    # Validate fused result
                    validation_results = FieldValidator.validate_all_fields(
                        {
                            "member_id": fused_result.member_id,
                            "member_name": fused_result.member_name,
                            "total_amount": fused_result.total_amount,
                            "service_date": fused_result.service_date,
                            "receipt_number": fused_result.receipt_number,
                            "provider_name": fused_result.provider_name,
                        }
                    )

                    # Log validation warnings
                    for field_name, result in validation_results.items():
                        if not result.is_valid:
                            logger.warning(
                                "Field validation failed after fusion",
                                job_id=job.id,
                                field=field_name,
                                errors=result.errors,
                            )

                    # Convert fused result back to ExtractionResult
                    extraction_result = self._convert_fused_to_extraction_result(
                        fused_result, extraction_result
                    )

                    # Store fusion metadata in job
                    fusion_metadata = {
                        "fusion_timestamp": fused_result.fusion_timestamp.isoformat(),
                        "conflicts_encountered": {
                            conflict.field_name: {
                                "email_value": conflict.email_value,
                                "email_confidence": conflict.email_confidence,
                                "ocr_value": conflict.ocr_value,
                                "ocr_confidence": conflict.ocr_confidence,
                                "resolution": conflict.resolution,
                                "reason": conflict.reason,
                            }
                            for conflict in fused_result.conflicts
                        },
                        "confidence_boosts_applied": fused_result.confidence_boosts,
                        "final_data_sources": fused_result.data_sources,
                        "fusion_strategy": "intelligent_field_preference",
                        "overall_confidence": fused_result.overall_confidence,
                        "confidence_level": fused_result.confidence_level,
                    }

                    logger.info(
                        "Data fusion complete",
                        job_id=job.id,
                        conflicts=len(fused_result.conflicts),
                        confidence_boost=sum(fused_result.confidence_boosts.values()),
                        final_confidence=fused_result.overall_confidence,
                    )

                except Exception as e:
                    logger.error(
                        "Data fusion failed, falling back to OCR-only",
                        job_id=job.id,
                        error=str(e),
                    )
                    fusion_metadata = {"error": str(e), "fallback": "ocr_only"}

            else:
                fusion_metadata = {"enabled": False}

            # Update job with extraction result and fusion metadata
            await self.queue_service.update_job_status(
                job.id,
                JobStatus.EXTRACTED,
                extraction_result=extraction_result,
            )

            # Get updated job
            job = await self.queue_service.get_job(job.id)

            # Update fusion metadata separately (if available)
            if fusion_metadata:
                job.fusion_metadata = fusion_metadata

            # Log to Sheets
            try:
                row_ref = await self.sheets_service.log_extraction(job, extraction_result)
                await self.queue_service.update_job_status(
                    job.id, JobStatus.EXTRACTED, sheets_row_ref=row_ref
                )
            except Exception as e:
                logger.error("Failed to log to Sheets", job_id=job.id, error=str(e))

            # Archive to Drive
            try:
                drive_file_id = await self.drive_service.archive_attachment(
                    image_path, job.email_id, job.attachment_filename
                )
                await self.queue_service.update_job_status(
                    job.id, JobStatus.EXTRACTED, drive_file_id=drive_file_id
                )
            except Exception as e:
                logger.error("Failed to archive to Drive", job_id=job.id, error=str(e))

            # Route based on confidence and QA sampling
            confidence = extraction_result.confidence_score

            # Check if job should be routed to exception queue
            should_route_to_exception = False
            exception_reason = None
            needs_review = False

            # Check confidence thresholds
            if confidence < settings.ocr.medium_confidence_threshold:
                # Low confidence - route to exception queue
                should_route_to_exception = True
                exception_reason = f"Low confidence: {confidence:.2%}"
                logger.warning(
                    "Low confidence extraction, routing to exception queue",
                    job_id=job.id,
                    confidence=confidence,
                    threshold=settings.ocr.medium_confidence_threshold,
                )

            elif confidence < settings.ocr.high_confidence_threshold:
                # Medium confidence - mark for review but proceed
                needs_review = True
                logger.info(
                    "Medium confidence extraction, marking for review",
                    job_id=job.id,
                    confidence=confidence,
                    medium_threshold=settings.ocr.medium_confidence_threshold,
                    high_threshold=settings.ocr.high_confidence_threshold,
                )

            else:
                # High confidence - check for QA random sampling
                qa_sample_rate = settings.ocr.qa_sampling_percentage
                if random.random() < qa_sample_rate:
                    needs_review = True
                    exception_reason = f"QA random sampling ({qa_sample_rate:.1%} rate)"
                    logger.info(
                        "High confidence extraction selected for QA sampling",
                        job_id=job.id,
                        confidence=confidence,
                        qa_sample_rate=qa_sample_rate,
                    )

            # Get fresh job data
            job = await self.queue_service.get_job(job.id)

            if should_route_to_exception:
                # Route to exception queue
                await self.queue_service.update_job_status(
                    job.id,
                    JobStatus.EXCEPTION,
                    exception_reason=exception_reason,
                    needs_review=True,
                )
                logger.info(
                    "Job routed to exception queue",
                    job_id=job.id,
                    reason=exception_reason,
                )

            else:
                # Proceed to NCB submission queue
                if needs_review:
                    await self.queue_service.update_job_status(
                        job.id,
                        JobStatus.EXTRACTED,
                        needs_review=True,
                        exception_reason=exception_reason,
                    )
                    logger.info(
                        "Job queued for submission with review flag",
                        job_id=job.id,
                        confidence=confidence,
                        review_reason=exception_reason or "Medium confidence",
                    )
                else:
                    logger.info(
                        "High confidence extraction, queuing for automatic submission",
                        job_id=job.id,
                        confidence=confidence,
                    )

                # Re-fetch job with updated metadata
                job = await self.queue_service.get_job(job.id)
                await self.queue_service.enqueue_job(
                    job, queue_name=settings.redis.submission_queue
                )

            # Cleanup temp file
            if image_path.exists():
                image_path.unlink()

            logger.info(
                "Job processing complete",
                job_id=job.id,
                confidence=confidence,
                status=job.status,
            )

        except Exception as e:
            logger.error("Job processing failed", job_id=job.id, error=str(e))
            await self.queue_service.update_job_status(
                job.id, JobStatus.FAILED, error_message=str(e)
            )

    def _get_email_extraction_from_job(self, job) -> Optional[EmailExtractionResult]:
        """
        Reconstruct EmailExtractionResult from job metadata.

        Args:
            job: Job object with email_extraction_metadata

        Returns:
            EmailExtractionResult or None if no email data available
        """
        if not job.email_extraction_metadata:
            logger.debug(
                "No email extraction metadata in job",
                job_id=job.id,
            )
            return None

        try:
            metadata = job.email_extraction_metadata

            # Reconstruct EmailExtractionResult from metadata
            email_extraction = EmailExtractionResult(
                member_id=metadata.get("member_id"),
                member_name=metadata.get("member_name"),
                provider_name=metadata.get("provider_name"),
                service_date=metadata.get("service_date"),
                receipt_number=metadata.get("receipt_number"),
                total_amount=metadata.get("total_amount"),
                gst_sst_amount=metadata.get("gst_sst_amount"),
                provider_address=metadata.get("provider_address"),
                policy_number=metadata.get("policy_number"),
                field_confidences=metadata.get("field_confidences", {}),
                extraction_methods=metadata.get("extraction_methods", {}),
                overall_confidence=metadata.get("email_extraction_confidence", 0.0),
                confidence_level=metadata.get("confidence_level", "low"),
                warnings=metadata.get("extraction_warnings", []),
                extracted_from_subject=metadata.get("fields_from_subject", []),
                extracted_from_body=metadata.get("fields_from_body", []),
            )

            logger.debug(
                "Reconstructed email extraction from job metadata",
                job_id=job.id,
                fields=len(email_extraction.field_confidences),
                confidence=email_extraction.overall_confidence,
            )

            return email_extraction

        except Exception as e:
            logger.error(
                "Failed to reconstruct email extraction from job metadata",
                job_id=job.id,
                error=str(e),
            )
            return None

    def _convert_fused_to_extraction_result(
        self, fused: FusedExtractionResult, original_ocr: ExtractionResult
    ) -> ExtractionResult:
        """
        Convert FusedExtractionResult to ExtractionResult for NCB submission.

        Args:
            fused: Fused extraction result
            original_ocr: Original OCR extraction result (for raw_text)

        Returns:
            ExtractionResult with fused data
        """
        # Create updated claim with fused data
        fused_claim = ExtractedClaim(
            member_id=fused.member_id,
            member_name=fused.member_name,
            policy_number=fused.policy_number,
            provider_name=fused.provider_name,
            provider_address=fused.provider_address,
            service_date=fused.service_date,
            receipt_number=fused.receipt_number,
            total_amount=fused.total_amount,
            currency="MYR",
            gst_amount=fused.gst_sst_amount if fused.gst_sst_amount else None,
            sst_amount=None,  # gst_sst_amount is already the combined value
            raw_text=original_ocr.claim.raw_text,  # Preserve original OCR raw text
            itemized_charges=original_ocr.claim.itemized_charges,  # Preserve itemized charges
        )

        # Create new ExtractionResult with fused claim
        fused_extraction = ExtractionResult(
            claim=fused_claim,
            confidence_score=fused.overall_confidence,
            confidence_level=fused.confidence_level,
            field_confidences=fused.field_confidences,
            warnings=fused.warnings,
            ocr_result=original_ocr.ocr_result,  # Preserve original OCR result
        )

        logger.debug(
            "Converted fused result to ExtractionResult",
            confidence=fused_extraction.confidence_score,
            level=fused_extraction.confidence_level,
        )

        return fused_extraction


async def main():
    """Entry point for OCR processor worker."""
    worker = OCRProcessorWorker()
    try:
        await worker.run()
    except KeyboardInterrupt:
        await worker.stop()


if __name__ == "__main__":
    asyncio.run(main())
