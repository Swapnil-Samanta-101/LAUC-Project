import os
import sys
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.pdfgen import canvas

REPORT_DIR = r"C:\Users\OneX1\LAUC Sem 1and2 FAP\report"
os.makedirs(REPORT_DIR, exist_ok=True)

DOCX_PATH = os.path.join(REPORT_DIR, "Simple_Review_Guide.docx")
PDF_PATH = os.path.join(REPORT_DIR, "Simple_Review_Guide.pdf")

# ==============================================================================
# 1. GENERATE DOCX
# ==============================================================================
def create_docx(filename):
    doc = Document()
    
    # Page setup
    for section in doc.sections:
        section.top_margin = Inches(0.8)
        section.bottom_margin = Inches(0.8)
        section.left_margin = Inches(0.8)
        section.right_margin = Inches(0.8)

    # Base styling
    normal_style = doc.styles['Normal']
    normal_style.font.name = 'Calibri'
    normal_style.font.size = Pt(11)
    normal_style.font.color.rgb = RGBColor(0x22, 0x22, 0x22)
    normal_style.paragraph_format.line_spacing = 1.15
    normal_style.paragraph_format.space_after = Pt(6)

    def set_cell_background(cell, fill_hex):
        tcPr = cell._tc.get_or_add_tcPr()
        shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
        tcPr.append(shd)

    def set_cell_margins(cell, top=120, bottom=120, left=180, right=180):
        tcPr = cell._tc.get_or_add_tcPr()
        tcMar = parse_xml(f'<w:tcMar {nsdecls("w")}><w:top w:w="{top}" w:type="dxa"/><w:bottom w:w="{bottom}" w:type="dxa"/><w:left w:w="{left}" w:type="dxa"/><w:right w:w="{right}" w:type="dxa"/></w:tcMar>')
        tcPr.append(tcMar)

    def add_callout(text, title="KEY TAKEAWAY", fill_hex="F0F4F8", border_hex="2563EB"):
        table = doc.add_table(rows=1, cols=1)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        table.autofit = False
        cell = table.cell(0, 0)
        cell.width = Inches(6.9)
        set_cell_background(cell, fill_hex)
        set_cell_margins(cell, top=140, bottom=140, left=200, right=200)
        
        tcPr = cell._tc.get_or_add_tcPr()
        borders = parse_xml(f'<w:tcBorders {nsdecls("w")}><w:left w:val="single" w:sz="24" w:space="0" w:color="{border_hex}"/><w:top w:val="none"/><w:right w:val="none"/><w:bottom w:val="none"/></w:tcBorders>')
        tcPr.append(borders)
        
        p = cell.paragraphs[0]
        p.paragraph_format.space_after = Pt(3)
        run_title = p.add_run(f"★ {title}\n")
        run_title.bold = True
        run_title.font.size = Pt(10)
        run_title.font.color.rgb = RGBColor(0x1E, 0x3A, 0x8A)
        
        run_text = p.add_run(text)
        run_text.font.size = Pt(10.5)
        run_text.font.color.rgb = RGBColor(0x33, 0x33, 0x33)
        doc.add_paragraph()

    def add_heading_1(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(16)
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(text)
        run.bold = True
        run.font.size = Pt(16)
        run.font.color.rgb = RGBColor(0x1E, 0x3A, 0x8A)
        return p

    def add_heading_2(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(12)
        p.paragraph_format.space_after = Pt(3)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(text)
        run.bold = True
        run.font.size = Pt(13)
        run.font.color.rgb = RGBColor(0x25, 0x63, 0xEB)
        return p

    def add_heading_3(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(8)
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(text)
        run.bold = True
        run.font.size = Pt(11.5)
        run.font.color.rgb = RGBColor(0x0F, 0x76, 0x6E)
        return p

    def add_bullet(p_or_text, bold_prefix="", text=""):
        p = doc.add_paragraph(style='List Bullet')
        p.paragraph_format.space_after = Pt(3)
        if bold_prefix:
            r_bold = p.add_run(bold_prefix)
            r_bold.bold = True
            r_bold.font.color.rgb = RGBColor(0x1F, 0x29, 0x37)
        if text:
            r_text = p.add_run(text)
            r_text.font.color.rgb = RGBColor(0x37, 0x41, 0x51)
        return p

    # --- Title Section ---
    p_title = doc.add_paragraph()
    p_title.paragraph_format.space_before = Pt(0)
    p_title.paragraph_format.space_after = Pt(4)
    run_title = p_title.add_run("Understanding the 2D CFD Wind Tunnel Simulator")
    run_title.bold = True
    run_title.font.size = Pt(22)
    run_title.font.color.rgb = RGBColor(0x0F, 0x29, 0x5A)

    p_sub = doc.add_paragraph()
    p_sub.paragraph_format.space_after = Pt(14)
    run_sub = p_sub.add_run("A Simple English Review & Complete Guide to the Program")
    run_sub.font.size = Pt(13)
    run_sub.font.color.rgb = RGBColor(0x4B, 0x55, 0x63)

    add_callout(
        "In plain words: This program is a virtual wind tunnel inside your computer. "
        "It lets you draw airplane wings or jet engine blades on your screen, blows digital air past them, "
        "calculates the real laws of physics in real time, and shows you how the air swirls and creates lift.",
        title="IN A NUTSHELL", fill_hex="EFF6FF", border_hex="3B82F6"
    )

    # --- Section 1: Executive Summary ---
    add_heading_1("1. What Is This Program?")
    doc.add_paragraph(
        "When engineers design airplanes or jet engines, they need to know how air flows around wings and blades. "
        "Traditionally, they build physical models out of metal and put them inside giant, noisy, expensive buildings called wind tunnels. "
        "Computational Fluid Dynamics (CFD) is the modern alternative: using math and computer code to simulate the air instead."
    )
    doc.add_paragraph(
        "This project, located in the folder 'LAUC Sem 1and2 FAP', is a complete, self-contained 2D CFD simulation system. "
        "Unlike complex industrial programs that require expensive software licenses or supercomputers, this entire system runs directly on a standard laptop in Python, "
        "accelerated by high-speed math tools, and streams the visual flow live into your web browser at http://127.0.0.1:8000."
    )

    # --- Section 2: The Three Main Building Blocks ---
    add_heading_1("2. The Three Big Parts of the Software")
    doc.add_paragraph("The entire application is organized into three cooperative parts, just like a modern video game:")

    add_bullet(None, "1. The Physics Engine (The 'Solver' folder): ", 
               "This is the mathematical brain. It divides the air into thousands of tiny grid squares and calculates speed, pressure, and friction dozens of times every second using the famous Navier-Stokes equations.")
    add_bullet(None, "2. The Geometry Creator (The 'Geometry' folder): ", 
               "This is the digital workshop. It draws the physical shapes you want to test—such as standard airplane wing cross-sections (NACA airfoils), rows of jet engine turbine blades (cascades), or simple round poles (cylinders).")
    add_bullet(None, "3. The Web Cockpit (The 'Web' folder): ", 
               "This is the dashboard you see in your web browser. It features buttons, sliders, real-time aerodynamic force gauges (lift and drag), and a smooth graphics canvas displaying colored flow fields and floating smoke trails.")

    # --- Section 3: How the Physics Work in Plain English ---
    add_heading_1("3. How the Simulation Works (The 4-Step Recipe)")
    doc.add_paragraph(
        "Fluid flow seems complicated, but inside this simulator, the computer follows a simple 4-step recipe over and over again, "
        "up to 60 times every second. This technique is known in physics as Chorin's Projection Method. Here is what happens in every split second:"
    )

    add_heading_2("Step 1: Coasting and Rubbing (Advection & Friction)")
    doc.add_paragraph(
        "Air has weight and momentum. When air is already moving, it wants to keep coasting forward (advection). "
        "At the same time, air is slightly sticky; layers of air sliding past each other experience friction and slow each other down (viscous diffusion). "
        "In Step 1, the program calculates where the air would drift based solely on its current momentum and friction."
    )

    add_heading_2("Step 2: Hitting Solid Walls (Brinkman Penalization)")
    doc.add_paragraph(
        "Air cannot pass through solid metal. Instead of building complicated, crooked mesh boundaries around the airplane wing, "
        "this program uses a clever trick called Brinkman volume penalization. Think of the solid wing as an invisible, ultra-dense sponge. "
        "Any air trying to enter the wing is immediately slowed to a complete halt (velocity = 0). It acts like an instant virtual brake inside the object, "
        "forcing the moving air to slide smoothly around the outside."
    )

    add_heading_2("Step 3: The 'No Squishing' Rule (Pressure & Incompressibility)")
    doc.add_paragraph(
        "At normal airplane flight speeds (subsonic speeds), air acts like water: it cannot be squished into a smaller space (incompressible). "
        "If Step 1 and Step 2 caused too much air to crowd into one tiny grid box, that box would unnaturally bulge. "
        "To prevent this, the program calculates pressure. Wherever air is bunching up, high pressure instantly develops to push air away. "
        "Wherever air is thinning out, low pressure pulls air in. "
        "The computer solves this huge puzzle for the entire room at once using a lightning-fast mathematical tool called Fast Fourier Transforms (FFT) and Cosine Transforms."
    )

    add_heading_2("Step 4: The Final Push (Velocity Correction)")
    doc.add_paragraph(
        "Finally, the simulator uses the pressure calculated in Step 3 to gently push every pocket of air. "
        "Now, every single particle moves at the correct speed, air glides cleanly around the wing, and no air squishes or disappears. "
        "The computer displays this updated picture on your screen, and then immediately begins Step 1 for the next split second!"
    )

    add_callout(
        "Summary of the 4-step cycle:\n"
        "1. Predict: Let the air coast forward and rub against neighbors.\n"
        "2. Block: Freeze any air that touched the solid wing.\n"
        "3. Pressure: Find the push forces so air never squishes or gaps.\n"
        "4. Correct: Apply the pressure push to get the true, smooth flow.",
        title="THE 4-STEP SIMULATION LOOP"
    )

    # --- Section 4: Why Is It So Fast? ---
    add_heading_1("4. Why Does It Run So Fast in Pure Python?")
    doc.add_paragraph(
        "Python is famously easy to write, but it is normally too slow for heavy scientific physics. "
        "This project achieves silky-smooth 30 to 60 frames per second using three powerful engineering techniques:"
    )

    add_bullet(None, "1. Numba JIT Compilation: ", 
               "Numba is a tool that reads Python math functions and translates them directly into raw computer machine code (C/C++ speed) the moment the program starts. The computer runs the inner physics at hardware speed.")
    add_bullet(None, "2. Spectral FFT Math Shortcuts: ", 
               "Normally, calculating pressure across 20,000 grid boxes requires guessing and correcting millions of times (relaxation). Instead, this program converts the problem into wave frequencies (using FFT and DCT), solves it in one single shot in ~1 millisecond, and converts it back!")
    add_bullet(None, "3. Staggered Grid Layout: ", 
               "Speeds are stored on the borders of each grid box, while pressure is stored dead-center. This prevents a famous computer illusion called 'checkerboarding', where the computer accidentally believes pressure is smooth when it is actually wildly oscillating.")

    # --- Section 5: The 4 Simulation Modes ---
    add_heading_1("5. The Four Things You Can Test (Simulation Modes)")
    doc.add_paragraph(
        "On the web control dashboard at http://127.0.0.1:8000, you can switch between four distinct aerodynamic experiments using a simple dropdown menu:"
    )

    table_modes = doc.add_table(rows=5, cols=3)
    table_modes.alignment = WD_TABLE_ALIGNMENT.CENTER
    table_modes.autofit = False

    headers = ["Mode Name", "What It Simulates", "Why It Matters in Real Life"]
    for i, h in enumerate(headers):
        cell = table_modes.cell(0, i)
        cell.paragraphs[0].text = h
        cell.paragraphs[0].runs[0].bold = True
        cell.paragraphs[0].runs[0].font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        set_cell_background(cell, "1E3A8A")
        set_cell_margins(cell, top=100, bottom=100, left=120, right=120)

    rows_data = [
        ("1. Airfoil Mode", "Flow over an airplane wing cross-section (NACA 4-digit series).", "You can tilt the wing (Angle of Attack) and see how lift pushes the wing up and drag pushes it back, until it stalls."),
        ("2. Turbofan Cascade", "Multiple jet engine blades stacked in a repeating row.", "Shows how jet engine fan blades bend incoming air (turning angle) to create engine thrust and compress air."),
        ("3. Cylinder Shedding", "Air blowing past a simple round pole or cable.", "Demonstrates the famous 'Kármán vortex street'—alternating whirlpools that can make telephone wires hum or bridges wobble!"),
        ("4. Lid-Driven Cavity", "Fluid trapped in a square box with a moving top lid.", "The world's standard benchmark test for fluid simulation software. Proves the math matches classic physics textbooks.")
    ]

    col_widths = [Inches(1.8), Inches(2.5), Inches(2.6)]
    for row_idx, data in enumerate(rows_data, start=1):
        for col_idx, text in enumerate(data):
            cell = table_modes.cell(row_idx, col_idx)
            cell.width = col_widths[col_idx]
            cell.paragraphs[0].text = text
            cell.paragraphs[0].paragraph_format.line_spacing = 1.15
            cell.paragraphs[0].paragraph_format.space_after = Pt(2)
            bg = "F8FAFC" if row_idx % 2 == 1 else "FFFFFF"
            set_cell_background(cell, bg)
            set_cell_margins(cell, top=80, bottom=80, left=100, right=100)

    doc.add_paragraph()

    # --- Section 6: Understanding the Web Controls ---
    add_heading_1("6. Guide to the Web Controls & Sliders")
    doc.add_paragraph(
        "When you look at the web dashboard in your browser, here is what each control knob does:"
    )

    add_bullet(None, "Reynolds Number (Re): ", 
               "Controls how 'sticky' or 'runny' the fluid is. Low numbers (like Re=100) act like thick syrup with smooth, steady flow. High numbers (like Re=2000+) act like thin, fast air with lively swirling eddies.")
    add_bullet(None, "Angle of Attack (Alpha): ", 
               "Tilts the airplane wing up or down. As you tilt up, lift increases. If you tilt too high (past ~15°), the air breaks away from the top surface—this is called an aerodynamic stall!")
    add_bullet(None, "NACA Code (e.g., 0012, 2412, 4412): ", 
               "A 4-digit code created by NASA's predecessor (NACA). '0012' means a perfectly symmetrical wing 12% thick. '2412' or '4412' adds curve (camber) to the wing so it generates lift even when level.")
    add_bullet(None, "Cascade Stagger & Pitch: ", 
               "Used in Jet Engine Cascade mode. 'Pitch' controls how close the fan blades are to each other; 'Stagger' controls the angle at which the blades are tilted.")
    add_bullet(None, "Display Field: ", 
               "Lets you switch views: 'Vorticity' colors the clockwise and counter-clockwise whirlpools in vivid red and blue; 'Speed' shows where air is fast or slow; 'Pressure' shows push zones.")
    add_bullet(None, "Smoke Particles: ", 
               "Releases 300 virtual smoke particles into the air tunnel so you can watch stream paths glide around the body like a real wind tunnel visualization.")

    # --- Section 7: File Guide ---
    add_heading_1("7. Plain-English Map of the Project Files")
    doc.add_paragraph("If you explore the project folder, here is what each file and folder does:")

    table_files = doc.add_table(rows=9, cols=2)
    table_files.alignment = WD_TABLE_ALIGNMENT.CENTER
    table_files.autofit = False

    f_headers = ["File / Folder Name", "Simple Purpose"]
    for i, h in enumerate(f_headers):
        cell = table_files.cell(0, i)
        cell.paragraphs[0].text = h
        cell.paragraphs[0].runs[0].bold = True
        cell.paragraphs[0].runs[0].font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        set_cell_background(cell, "0F766E")
        set_cell_margins(cell, top=80, bottom=80, left=120, right=120)

    f_data = [
        ("web / server.py", "The web server built with FastAPI. It runs the simulation and sends updates to your browser via a WebSocket pipe."),
        ("web / static / index.html", "The webpage user interface (buttons, dials, sliders, gauges, and drawing canvas)."),
        ("web / static / app.js", "The browser code that draws the colors, paints the airplane wing, and moves the smoke particles."),
        ("solver / ns_solver.py", "The orchestrator. It manages the 4-step physics recipe and calculates time step sizes."),
        ("solver / grid.py", "Creates the rectangular grid of calculation points (like dividing a whiteboard into squares)."),
        ("solver / poisson.py", "The spectral math solver that calculates pressure across the whole grid in 1 millisecond."),
        ("geometry / naca.py", "Calculates the exact curved coordinates of NASA airfoil shapes from a 4-digit number."),
        ("geometry / cascade.py", "Generates the geometry for rows of repeating turbofan blades in jet engines.")
    ]

    f_widths = [Inches(2.5), Inches(4.4)]
    for row_idx, data in enumerate(f_data, start=1):
        for col_idx, text in enumerate(data):
            cell = table_files.cell(row_idx, col_idx)
            cell.width = f_widths[col_idx]
            cell.paragraphs[0].text = text
            cell.paragraphs[0].paragraph_format.line_spacing = 1.15
            cell.paragraphs[0].paragraph_format.space_after = Pt(2)
            bg = "F0FDFA" if row_idx % 2 == 1 else "FFFFFF"
            set_cell_background(cell, bg)
            set_cell_margins(cell, top=70, bottom=70, left=100, right=100)

    doc.add_paragraph()

    # --- Section 8: Final Review & Conclusion ---
    add_heading_1("8. Final Review & Verdict")
    doc.add_paragraph(
        "In summary, this program is an exceptional educational and engineering simulation tool. "
        "Here is an honest review of its strengths and learning value:"
    )

    add_bullet(None, "★ Ease of Use: ", "You don't need CAD software or terminal expertise. You open a normal web link (http://127.0.0.1:8000), move sliders, and immediately see the results.")
    add_bullet(None, "★ Scientific Accuracy: ", "It does not cheat or use cartoon physics. It solves the genuine Navier-Stokes fluid equations and passes verified scientific benchmark tests.")
    add_bullet(None, "★ High Performance: ", "By combining Python's simplicity with Numba's hardware compilation and FFT spectral math, it achieves fluid simulation speeds normally reserved for expensive C++ commercial packages.")
    add_bullet(None, "★ Educational Insight: ", "It makes invisible air visible. Students and aerospace enthusiasts can directly watch how changing an airfoil's curve or angle changes lift, drag, and wake turbulence.")

    doc.save(filename)
    print(f"Successfully generated DOCX at: {filename}")


# ==============================================================================
# 2. GENERATE PDF WITH REPORTLAB
# ==============================================================================
class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            super().showPage()
        super().save()

    def draw_page_number(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 9)
        self.setFillColor(colors.HexColor("#64748B"))
        
        # Header (pages > 1)
        if self._pageNumber > 1:
            self.drawString(54, 750, "2D Navier-Stokes CFD Simulator — Simple Review & Guide")
            self.setStrokeColor(colors.HexColor("#E2E8F0"))
            self.setLineWidth(0.5)
            self.line(54, 742, 558, 742)
            
        # Footer
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(558, 36, page_str)
        self.drawString(54, 36, "LAUC Sem 1 & 2 FAP — Interactive Aerodynamics Suite")
        self.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.setLineWidth(0.5)
        self.line(54, 48, 558, 48)
        self.restoreState()


def create_pdf(filename):
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )
    
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#0F295A"),
        spaceAfter=4
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubTitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#4B5563"),
        spaceAfter=12
    )

    h1_style = ParagraphStyle(
        'Heading1_Custom',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=18,
        textColor=colors.HexColor("#1E3A8A"),
        spaceBefore=14,
        spaceAfter=6,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'Heading2_Custom',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=11.5,
        leading=15,
        textColor=colors.HexColor("#2563EB"),
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'Body_Custom',
        parent=styles['BodyText'],
        fontName='Helvetica',
        fontSize=10,
        leading=14.5,
        textColor=colors.HexColor("#1F2937"),
        spaceAfter=6
    )

    bullet_style = ParagraphStyle(
        'Bullet_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13.5,
        textColor=colors.HexColor("#374151"),
        leftIndent=14,
        firstLineIndent=-10,
        spaceAfter=4
    )

    callout_style = ParagraphStyle(
        'Callout_Text',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13.5,
        textColor=colors.HexColor("#1E293B")
    )
    
    callout_title = ParagraphStyle(
        'Callout_Title',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor("#1E3A8A"),
        spaceAfter=3
    )

    table_header_style = ParagraphStyle(
        'TableHeader',
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=colors.white
    )

    table_cell_style = ParagraphStyle(
        'TableCell',
        fontName='Helvetica',
        fontSize=8.5,
        leading=11.5,
        textColor=colors.HexColor("#1F2937")
    )

    story = []

    # Title
    story.append(Paragraph("Understanding the 2D CFD Wind Tunnel Simulator", title_style))
    story.append(Paragraph("A Simple English Review & Complete Guide to the Program", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#3B82F6"), spaceAfter=10))

    # In a Nutshell Box
    callout_content = [
        [Paragraph("<b>★ IN A NUTSHELL</b>", callout_title)],
        [Paragraph(
            "<b>In plain words:</b> This program is a virtual wind tunnel inside your computer. "
            "It lets you draw airplane wings or jet engine blades on your screen, blows digital air past them, "
            "calculates the real laws of physics in real time, and shows you how the air swirls and creates lift.",
            callout_style
        )]
    ]
    t_box = Table(callout_content, colWidths=[504])
    t_box.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#EFF6FF")),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#BFDBFE")),
        ('LINELEFT', (0, 0), (0, -1), 3.5, colors.HexColor("#3B82F6")),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(t_box)
    story.append(Spacer(1, 10))

    # Section 1
    story.append(Paragraph("1. What Is This Program?", h1_style))
    story.append(Paragraph(
        "When engineers design airplanes or jet engines, they need to know how air flows around wings and blades. "
        "Traditionally, they build physical models out of metal and put them inside giant, noisy, expensive buildings called wind tunnels. "
        "<b>Computational Fluid Dynamics (CFD)</b> is the modern computer alternative: using math and code to simulate the air instead.",
        body_style
    ))
    story.append(Paragraph(
        "This project, located in the folder <i>LAUC Sem 1and2 FAP</i>, is a complete, self-contained 2D CFD simulation system. "
        "Unlike complex industrial programs that require expensive software licenses or supercomputers, this entire system runs directly on a standard laptop in Python, "
        "accelerated by high-speed math tools, and streams the visual flow live into your web browser at <b>http://127.0.0.1:8000</b>.",
        body_style
    ))

    # Section 2
    story.append(Paragraph("2. The Three Big Parts of the Software", h1_style))
    story.append(Paragraph("The entire application is organized into three cooperative parts:", body_style))
    story.append(Paragraph("• <b>The Physics Engine (solver/):</b> The mathematical brain. It divides the air into thousands of tiny grid squares and calculates speed, pressure, and friction dozens of times every second using the Navier-Stokes equations.", bullet_style))
    story.append(Paragraph("• <b>The Geometry Creator (geometry/):</b> The digital workshop. It draws the physical shapes you want to test—such as standard airplane wing cross-sections (NACA airfoils), rows of jet engine turbine blades (cascades), or simple round poles (cylinders).", bullet_style))
    story.append(Paragraph("• <b>The Web Cockpit (web/):</b> The dashboard you see in your web browser. It features buttons, sliders, real-time aerodynamic force gauges (lift and drag), and a smooth graphics canvas displaying colored flow fields and floating smoke trails.", bullet_style))

    # Section 3
    story.append(Paragraph("3. How the Simulation Works (The 4-Step Recipe)", h1_style))
    story.append(Paragraph(
        "Fluid flow seems complicated, but inside this simulator, the computer follows a simple 4-step recipe over and over again, "
        "up to 60 times every second. This technique is known in physics as <i>Chorin's Projection Method</i>:",
        body_style
    ))
    
    story.append(Paragraph("Step 1: Coasting and Rubbing (Advection & Friction)", h2_style))
    story.append(Paragraph(
        "Air has weight and momentum. When air is already moving, it wants to keep coasting forward (advection). "
        "At the same time, air is slightly sticky; layers of air sliding past each other experience friction and slow each other down (viscous diffusion). "
        "In Step 1, the program calculates where the air would drift based solely on its current momentum and friction.",
        body_style
    ))

    story.append(Paragraph("Step 2: Hitting Solid Walls (Brinkman Penalization)", h2_style))
    story.append(Paragraph(
        "Air cannot pass through solid metal. Instead of building complicated, crooked mesh boundaries around the airplane wing, "
        "this program uses a clever trick called Brinkman volume penalization. Think of the solid wing as an invisible, ultra-dense sponge. "
        "Any air trying to enter the wing is immediately slowed to a complete halt (velocity = 0). It acts like an instant virtual brake inside the object, "
        "forcing the moving air to slide smoothly around the outside.",
        body_style
    ))

    story.append(Paragraph("Step 3: The 'No Squishing' Rule (Pressure & Incompressibility)", h2_style))
    story.append(Paragraph(
        "At normal airplane flight speeds (subsonic speeds), air acts like water: it cannot be squished into a smaller space (incompressible). "
        "If Step 1 and Step 2 caused too much air to crowd into one tiny grid box, that box would unnaturally bulge. "
        "To prevent this, the program calculates pressure. Wherever air is bunching up, high pressure instantly develops to push air away. "
        "Wherever air is thinning out, low pressure pulls air in. "
        "The computer solves this huge puzzle for the entire room at once using a lightning-fast mathematical tool called Fast Fourier Transforms (FFT) and Cosine Transforms.",
        body_style
    ))

    story.append(Paragraph("Step 4: The Final Push (Velocity Correction)", h2_style))
    story.append(Paragraph(
        "Finally, the simulator uses the pressure calculated in Step 3 to gently push every pocket of air. "
        "Now, every single particle moves at the correct speed, air glides cleanly around the wing, and no air squishes or disappears. "
        "The computer displays this updated picture on your screen, and then immediately begins Step 1 for the next split second!",
        body_style
    ))

    # Section 4
    story.append(Paragraph("4. Why Does It Run So Fast in Pure Python?", h1_style))
    story.append(Paragraph("This project achieves silky-smooth 30 to 60 frames per second using three powerful engineering techniques:", body_style))
    story.append(Paragraph("• <b>Numba JIT Compilation:</b> Translates Python math directly into raw computer machine code (C/C++ speed) the moment the program starts. The inner physics runs at hardware speed.", bullet_style))
    story.append(Paragraph("• <b>Spectral FFT Math Shortcuts:</b> Normally, solving pressure across 20,000 grid boxes requires guessing and correcting millions of times. Instead, this program converts the problem into wave frequencies (using FFT and DCT), solves it in one shot in ~1 millisecond, and converts it back!", bullet_style))
    story.append(Paragraph("• <b>Staggered Grid Layout:</b> Speeds are stored on the borders of each grid box, while pressure is stored dead-center. This prevents the computer from getting confused by checkerboard oscillations.", bullet_style))

    # Section 5
    story.append(Paragraph("5. The Four Things You Can Test (Simulation Modes)", h1_style))
    story.append(Paragraph("On the web dashboard at <b>http://127.0.0.1:8000</b>, you can switch between four distinct aerodynamic experiments:", body_style))

    table_data = [
        [Paragraph("<b>Mode Name</b>", table_header_style), Paragraph("<b>What It Simulates</b>", table_header_style), Paragraph("<b>Why It Matters in Real Life</b>", table_header_style)],
        [Paragraph("<b>1. Airfoil Mode</b>", table_cell_style), Paragraph("Flow over an airplane wing cross-section (NACA 4-digit series).", table_cell_style), Paragraph("Tilt the wing (Angle of Attack) and see how lift pushes the wing up and drag pushes it back, until it stalls.", table_cell_style)],
        [Paragraph("<b>2. Turbofan Cascade</b>", table_cell_style), Paragraph("Multiple jet engine blades stacked in a repeating row.", table_cell_style), Paragraph("Shows how jet engine fan blades bend incoming air (turning angle) to create engine thrust and compress air.", table_cell_style)],
        [Paragraph("<b>3. Cylinder Shedding</b>", table_cell_style), Paragraph("Air blowing past a simple round pole or cable.", table_cell_style), Paragraph("Demonstrates the famous 'Kármán vortex street'—alternating whirlpools that make wires hum or bridges wobble!", table_cell_style)],
        [Paragraph("<b>4. Lid-Driven Cavity</b>", table_cell_style), Paragraph("Fluid trapped in a square box with a moving top lid.", table_cell_style), Paragraph("The world's standard benchmark test for fluid simulation software. Proves the math matches classic physics textbooks.", table_cell_style)]
    ]
    t_modes = Table(table_data, colWidths=[110, 194, 200])
    t_modes.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor("#F8FAFC"), colors.white]),
    ]))
    story.append(t_modes)
    story.append(Spacer(1, 10))

    # Section 6
    story.append(Paragraph("6. Guide to the Web Controls & Sliders", h1_style))
    story.append(Paragraph("• <b>Reynolds Number (Re):</b> Controls how 'sticky' or 'runny' the fluid is. Low numbers (like Re=100) act like thick syrup with smooth flow. High numbers (like Re=2000+) act like thin air with lively swirling eddies.", bullet_style))
    story.append(Paragraph("• <b>Angle of Attack (Alpha):</b> Tilts the airplane wing up or down. As you tilt up, lift increases. If you tilt too high (past ~15°), the air separates from the top—causing an aerodynamic stall!", bullet_style))
    story.append(Paragraph("• <b>NACA Code (e.g., 0012, 2412, 4412):</b> Symmetrical vs curved wings. '0012' is symmetrical; '2412' or '4412' adds camber (curve) to create lift even when level.", bullet_style))
    story.append(Paragraph("• <b>Display Field:</b> Switch between 'Vorticity' (red/blue whirlpools), 'Speed' (rainbow velocity), and 'Pressure' (push forces).", bullet_style))
    story.append(Paragraph("• <b>Smoke Particles:</b> Releases 300 floating smoke particles so you can watch stream paths glide around the body like in a real wind tunnel.", bullet_style))

    # Section 7
    story.append(Paragraph("7. Final Review & Verdict", h1_style))
    story.append(Paragraph(
        "In summary, this program is an exceptional educational and engineering simulation tool. "
        "It successfully balances genuine scientific rigor with high responsiveness and an intuitive visual interface.",
        body_style
    ))
    story.append(Paragraph("• <b>Ease of Use:</b> No CAD software or terminal expertise required. Open <i>http://127.0.0.1:8000</i>, move sliders, and watch immediate feedback.", bullet_style))
    story.append(Paragraph("• <b>Scientific Accuracy:</b> It uses the real incompressible Navier-Stokes equations and passes rigorous academic benchmark tests (Ghia cavity & Karman shedding).", bullet_style))
    story.append(Paragraph("• <b>High Performance:</b> By pairing Python with Numba and FFT spectral math, it delivers real-time interactivity on standard computer hardware.", bullet_style))
    story.append(Paragraph("• <b>Educational Power:</b> It transforms abstract fluid equations into living, colored fluid flows that make aerodynamic concepts instantly understandable.", bullet_style))

    # Build PDF
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Successfully generated PDF at: {filename}")


if __name__ == "__main__":
    create_docx(DOCX_PATH)
    create_pdf(PDF_PATH)
