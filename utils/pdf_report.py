from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from datetime import datetime
from io import BytesIO
import cv2


def generate_scan_report(
    pdf_path: str,
    annotated_bgr_image,
    tray_avg_score: float,
    tray_grade: str,
    price_per_kg: float,
    kernel_results: list,
):
    """
    annotated_bgr_image: OpenCV BGR image (numpy array)
    """

    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")

    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    story = []

    # ---------- counts ----------
    defect_counts = {}
    class_counts = {}

    defect_counts = {}
    class_counts = {}

    for k in (kernel_results or []):
        g = k.get("grade", "Unknown")
        class_counts[g] = class_counts.get(g, 0) + 1

        for d in k.get("defects", []):
            label = str(d.get("label", "")).lower()  # use label string
            if label:
                defect_counts[label] = defect_counts.get(label, 0) + 1

    detected = len(kernel_results or [])

    # Update defect order to match the model's classes
    defect_order = ["damage", "shriveled", "broken"]   # as defined in PENALTY
    grade_order = ["Extra Class", "Class I", "Class II", "Reject / Non-trade"]

    # ---------- title ----------
    story.append(Paragraph("<b>Mani-to-Money : Peanut Kernel Classifier</b>", styles["Title"]))
    story.append(Spacer(1, 10))

    # ---------- scan summary ----------
    story.append(Paragraph("<b>SCAN SUMMARY</b>", styles["Heading2"]))
    story.append(Paragraph(f"Date: {date_str}", styles["Normal"]))
    story.append(Paragraph(f"Time: {time_str}", styles["Normal"]))
    story.append(Spacer(1, 10))

    # ---------- optional image ----------
    if annotated_bgr_image is not None:
        try:
            success, buf = cv2.imencode(".png", annotated_bgr_image)
            if success:
                img_stream = BytesIO(buf.tobytes())
                pdf_img = Image(img_stream, width=16 * cm, height=9 * cm)
                pdf_img.hAlign = "CENTER"
                story.append(pdf_img)
                story.append(Spacer(1, 10))
        except Exception:
            pass

    # ---------- handle empty detection ----------
    if detected == 0:
        story.append(Paragraph("<b>NOTICE</b>", styles["Heading2"]))
        story.append(Paragraph("No peanut kernels detected. Try again with better lighting/position.", styles["Normal"]))
        doc.build(story)
        return

    # ---------- defect counts ----------
    story.append(Paragraph("<b>DEFECT COUNTS</b>", styles["Heading2"]))
    for d in defect_order:
        story.append(Paragraph(f"{d}: {defect_counts.get(d, 0)}", styles["Normal"]))
    story.append(Spacer(1, 10))

    # ---------- kernels per class ----------
    story.append(Paragraph("<b>KERNELS PER CLASS</b>", styles["Heading2"]))
    story.append(Paragraph(f"Detected kernels: {detected}", styles["Normal"]))
    for g in grade_order:
        story.append(Paragraph(f"{g}: {class_counts.get(g, 0)}", styles["Normal"]))
    story.append(Spacer(1, 10))

    # ---------- final numbers ----------
    story.append(Paragraph(f"Tray Avg Score: {tray_avg_score:.2f}", styles["Normal"]))
    story.append(Paragraph(f"Tray Avg Grade: {tray_grade}", styles["Normal"]))
    story.append(Paragraph(f"Estimated Price per Kg: ₱{price_per_kg:.2f} per kg", styles["Normal"]))

    doc.build(story)