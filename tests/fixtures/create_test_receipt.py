#!/usr/bin/env python3
"""Generate a test Malaysian receipt image for OCR testing."""

from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

def create_malaysian_receipt():
    """Create a realistic Malaysian medical receipt."""
    # Create image (A5 size at 150dpi)
    width, height = 1240, 1748
    img = Image.new('RGB', (width, height), color='white')
    draw = ImageDraw.Draw(img)

    # Try to use default font, fallback to basic if not available
    try:
        # Try to get a reasonable sized font
        title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
        header_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
        body_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
        small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
    except:
        # Fallback to default
        title_font = ImageFont.load_default()
        header_font = ImageFont.load_default()
        body_font = ImageFont.load_default()
        small_font = ImageFont.load_default()

    y = 50

    # Clinic name (in bold)
    draw.text((width//2, y), "KLINIK MEDIVIRON", fill='black', font=title_font, anchor='mt')
    y += 60

    # Address
    draw.text((width//2, y), "123, Jalan Bukit Bintang", fill='black', font=small_font, anchor='mt')
    y += 35
    draw.text((width//2, y), "55100 Kuala Lumpur", fill='black', font=small_font, anchor='mt')
    y += 35
    draw.text((width//2, y), "Tel: 03-21234567", fill='black', font=small_font, anchor='mt')
    y += 50

    # Separator
    draw.line([(100, y), (width-100, y)], fill='black', width=2)
    y += 40

    # Receipt header
    draw.text((width//2, y), "TAX INVOICE / RESIT", fill='black', font=header_font, anchor='mt')
    y += 50

    # Receipt details
    details = [
        ("Receipt No:", "INV-2024-001234"),
        ("Date:", "24/12/2024"),
        ("Time:", "14:30"),
        ("", ""),
        ("Patient Name:", "Ahmad bin Abdullah"),
        ("Member ID:", "MEM123456789"),
        ("Policy No:", "POL987654321"),
    ]

    for label, value in details:
        if label:
            draw.text((150, y), label, fill='black', font=body_font)
            draw.text((width-150, y), value, fill='black', font=body_font, anchor='rt')
        y += 40

    y += 20

    # Items separator
    draw.line([(100, y), (width-100, y)], fill='black', width=1)
    y += 40

    # Service items
    draw.text((150, y), "SERVICES", fill='black', font=header_font)
    y += 50

    items = [
        ("Consultation Fee", "RM 50.00"),
        ("Blood Test - Full Panel", "RM 180.00"),
        ("X-Ray", "RM 120.00"),
        ("Medication", "RM 85.50"),
    ]

    for item, price in items:
        draw.text((150, y), item, fill='black', font=body_font)
        draw.text((width-150, y), price, fill='black', font=body_font, anchor='rt')
        y += 40

    y += 20
    draw.line([(100, y), (width-100, y)], fill='black', width=1)
    y += 40

    # Totals
    totals = [
        ("Subtotal:", "RM 435.50"),
        ("SST (10%):", "RM 43.55"),
        ("", ""),
    ]

    for label, value in totals:
        if label:
            draw.text((width-500, y), label, fill='black', font=body_font)
            draw.text((width-150, y), value, fill='black', font=body_font, anchor='rt')
        y += 40

    # Grand total (highlighted)
    draw.rectangle([(width-600, y-10), (width-100, y+50)], outline='black', width=3)
    draw.text((width-500, y+5), "TOTAL:", fill='black', font=header_font)
    draw.text((width-150, y+5), "RM 479.05", fill='black', font=header_font, anchor='rt')
    y += 80

    # Footer
    y += 40
    draw.line([(100, y), (width-100, y)], fill='black', width=1)
    y += 40

    footer_text = [
        "Payment Method: Cash",
        "Thank you for visiting Klinik Mediviron",
        "Please keep this receipt for insurance claims",
    ]

    for text in footer_text:
        draw.text((width//2, y), text, fill='black', font=small_font, anchor='mt')
        y += 35

    # Save image
    output_path = Path(__file__).parent / "malaysian_receipt_test.jpg"
    img.save(output_path, "JPEG", quality=95)
    print(f"✅ Created test receipt: {output_path}")
    return output_path

if __name__ == "__main__":
    create_malaysian_receipt()
