#!/usr/bin/env python3
"""
Email Text Extraction Demo

Demonstrates the EmailTextExtractor capabilities with real-world examples.
"""

import sys
sys.path.insert(0, '/home/dra/projects/ncb_OCR')

from src.utils.email_text_extractor import extract_email_text, EmailTextExtractor


def demo_basic_html():
    """Demo: Basic HTML extraction."""
    print("=" * 70)
    print("DEMO 1: Basic HTML Extraction")
    print("=" * 70)

    html = """
    <html>
    <body>
        <h1>Medical Claim</h1>
        <p>Please process my claim for:</p>
        <ul>
            <li><strong>Member ID:</strong> M123456</li>
            <li><strong>Amount:</strong> RM 85.50</li>
            <li><strong>Date:</strong> 15/12/2024</li>
        </ul>
    </body>
    </html>
    """

    result = extract_email_text(html, 'text/html')

    print(f"\nInput (HTML):\n{html}")
    print(f"\nOutput (Plain Text):\n{result}")
    print()


def demo_signature_removal():
    """Demo: Email signature removal."""
    print("=" * 70)
    print("DEMO 2: Signature Removal")
    print("=" * 70)

    email_with_sig = """
    Dear Claims Team,

    Please find my medical receipt attached.

    Member ID: M789012
    Service Date: 20/12/2024
    Amount: RM 120.00

    --
    Best regards,
    Ahmad bin Abdullah
    +60-12-345-6789

    Sent from my iPhone
    """

    result = extract_email_text(email_with_sig, 'text/plain')

    print(f"\nInput (With Signature):\n{email_with_sig}")
    print(f"\nOutput (Signature Removed):\n{result}")
    print()


def demo_multipart_email():
    """Demo: Multipart email (plain + HTML)."""
    print("=" * 70)
    print("DEMO 3: Multipart Email (Prefers Plain Text)")
    print("=" * 70)

    extractor = EmailTextExtractor()

    parts = [
        ('text/html', '<p><b>HTML Version:</b> Member ID M555555</p>'),
        ('text/plain', 'Plain Text Version: Member ID M555555'),
    ]

    result = extractor.extract_from_multipart(parts)

    print(f"\nParts:")
    for mime_type, content in parts:
        print(f"  {mime_type}: {content[:50]}...")

    print(f"\nExtracted (Prefers Plain):\n{result}")
    print()


def demo_real_malaysian_claim():
    """Demo: Real Malaysian medical claim email."""
    print("=" * 70)
    print("DEMO 4: Malaysian Medical Claim Email")
    print("=" * 70)

    malaysian_claim = """
    <html>
    <head><title>Tuntutan Perubatan</title></head>
    <body>
        <div style="font-family: Arial, sans-serif;">
            <h2>Tuntutan Perubatan / Medical Claim</h2>

            <p><strong>Maklumat Ahli / Member Information:</strong></p>
            <table>
                <tr><td>ID Ahli / Member ID:</td><td>M987654</td></tr>
                <tr><td>Nama / Name:</td><td>Siti Nurhaliza</td></tr>
            </table>

            <p><strong>Butiran Rawatan / Treatment Details:</strong></p>
            <ul>
                <li>Klinik / Clinic: <strong>Klinik Kesihatan Prima</strong></li>
                <li>Tarikh Perkhidmatan / Service Date: <strong>22/12/2024</strong></li>
                <li>Jenis Rawatan / Treatment Type: <strong>Konsultasi Doktor</strong></li>
            </ul>

            <p><strong>Kos / Cost:</strong></p>
            <ul>
                <li>Bayaran Konsultasi / Consultation Fee: RM 60.00</li>
                <li>Ubat-ubatan / Medication: RM 25.50</li>
                <li>SST (10%): RM 8.55</li>
                <li><strong>Jumlah / Total: RM 94.05</strong></li>
            </ul>

            <p>Resit dilampirkan. / Receipt attached.</p>

            <p>Terima kasih. / Thank you.</p>
        </div>
        <hr>
        <p style="color: gray; font-size: 0.8em;">
            Siti Nurhaliza<br>
            siti@example.com<br>
            +60-11-2345-6789<br>
            <br>
            Sent from my Android
        </p>
    </body>
    </html>
    """

    result = extract_email_text(malaysian_claim, 'text/html')

    print(f"\nInput: Malaysian bilingual HTML email")
    print(f"Length: {len(malaysian_claim)} characters")

    print(f"\nExtracted Text:\n{result}")
    print(f"\nExtracted Length: {len(result)} characters")
    print(f"Reduction: {((len(malaysian_claim) - len(result)) / len(malaysian_claim) * 100):.1f}%")

    # Verify key info extracted
    print("\n✅ Verification:")
    checks = {
        'Member ID': 'M987654' in result,
        'Member Name': 'Siti Nurhaliza' in result,
        'Clinic Name': 'Klinik Kesihatan Prima' in result,
        'Service Date': '22/12/2024' in result,
        'Total Amount': 'RM 94.05' in result,
        'SST Tax': 'SST' in result,
        'HTML Removed': '<html>' not in result and '<p>' not in result,
        'Signature Removed': 'Sent from my Android' not in result,
    }

    for check, passed in checks.items():
        status = '✓' if passed else '✗'
        print(f"  {status} {check}")

    print()


def demo_whitespace_normalization():
    """Demo: Whitespace normalization."""
    print("=" * 70)
    print("DEMO 5: Whitespace Normalization")
    print("=" * 70)

    messy_text = """


    This   text   has      too    many




    spaces   and   newlines.


    It  needs   cleaning.


    """

    result = extract_email_text(messy_text, 'text/plain')

    print(f"Input (messy):\n{repr(messy_text)}")
    print(f"\nOutput (cleaned):\n{repr(result)}")
    print(f"\nReadable Output:\n{result}")
    print()


def main():
    """Run all demos."""
    print("\n")
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 15 + "EMAIL TEXT EXTRACTION DEMOS" + " " * 26 + "║")
    print("╚" + "═" * 68 + "╝")
    print()

    demo_basic_html()
    demo_signature_removal()
    demo_multipart_email()
    demo_real_malaysian_claim()
    demo_whitespace_normalization()

    print("=" * 70)
    print("All demos completed successfully! ✅")
    print("=" * 70)
    print()


if __name__ == '__main__':
    main()
