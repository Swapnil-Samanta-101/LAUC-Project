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

REPORT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(REPORT_DIR)
os.makedirs(REPORT_DIR, exist_ok=True)

DOCX_PATH = os.path.join(REPORT_DIR, "Code_Architecture_Guide.docx")
PDF_PATH = os.path.join(REPORT_DIR, "Code_Architecture_Guide.pdf")

ROOT_DOCX = os.path.join(PROJECT_ROOT, "Code_Architecture_Guide.docx")
ROOT_PDF = os.path.join(PROJECT_ROOT, "Code_Architecture_Guide.pdf")


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

    def add_callout(text, title="KEY CONCEPT", fill_hex="F0F4F8", border_hex="2563EB"):
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

    def add_bullet(bold_prefix="", text=""):
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

    def add_code_snippet(code_text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(4)
        p.paragraph_format.space_after = Pt(6)
        p.paragraph_format.left_indent = Inches(0.25)
        run = p.add_run(code_text)
        run.font.name = 'Consolas'
        run.font.size = Pt(9.5)
        run.font.color.rgb = RGBColor(0x1F, 0x29, 0x37)

    # --- Title Section ---
    p_title = doc.add_paragraph()
    p_title.paragraph_format.space_before = Pt(0)
    p_title.paragraph_format.space_after = Pt(4)
    run_title = p_title.add_run("The Code Behind the Simulator")
    run_title.bold = True
    run_title.font.size = Pt(22)
    run_title.font.color.rgb = RGBColor(0x0F, 0x29, 0x5A)

    p_sub = doc.add_paragraph()
    p_sub.paragraph_format.space_after = Pt(14)
    run_sub = p_sub.add_run("A Simple English Developer & Code Architecture Guide")
    run_sub.font.size = Pt(13)
    run_sub.font.color.rgb = RGBColor(0x4B, 0x55, 0x63)

    add_callout(
        "This guide explains exactly how the code works under the hood: how the Python math functions, "
        "Numba compiler, FastAPI web server, and browser JavaScript connect together to simulate fluid flow in real time.",
        title="ABOUT THIS DOCUMENT", fill_hex="EFF6FF", border_hex="3B82F6"
    )

    # --- Section 1: The Full Picture ---
    add_heading_1("1. The Big Picture: How Data Flows Through the Code")
    doc.add_paragraph(
        "To understand this software, follow the path of a single user action—for example, when you move the 'Angle of Attack' slider in your browser:"
    )

    add_bullet("1. User Action in Browser: ", "You drag the slider on index.html. JavaScript in app.js captures this event and sends a tiny JSON message over a live WebSocket connection to the Python backend.")
    add_bullet("2. Web Server Reception: ", "server.py receives the message inside websocket_endpoint(). It passes the new angle to SimulationManager, which instantly calls geometry/naca.py to compute new wing coordinates.")
    add_bullet("3. Solid Mask Creation: ", "geometry/penalization.py computes a 2D mask of 1s (inside the wing) and 0s (in the air). This mask is given to solver/ns_solver.py.")
    add_bullet("4. High-Speed Physics Calculation: ", "ns_solver.py runs one time step. It calls advection.py (momentum), diffusion.py (friction), and poisson.py (pressure). Thanks to Numba's @njit decorator, these calculations execute in pure machine code at hardware speed.")
    add_bullet("5. Encoding & Streaming Back: ", "server.py takes the 2D grid of fluid speeds, turns the numbers into a compact base64 byte array, and sends it back across the WebSocket.")
    add_bullet("6. Canvas Painting: ", "app.js receives the byte array, maps each number to a color (blue for slow, red for fast or swirling), paints it onto the HTML5 <canvas>, and nudges 300 virtual smoke particles forward!")

    # --- Section 2: solver/grid.py ---
    add_heading_1("2. The Grid System (solver/grid.py)")
    doc.add_paragraph(
        "How do you store continuous air inside a computer? You divide the simulation box into a grid of tiny rectangles. "
        "However, this program does something special called a Marker-and-Cell (MAC) Staggered Grid."
    )
    
    add_heading_2("Why Stagger the Grid?")
    doc.add_paragraph(
        "If you put horizontal speed (u), vertical speed (v), and pressure (p) all in the exact same center spot of each box, "
        "a terrible numerical bug can happen called 'checkerboarding'. The pressure can wildly jump up-and-down (+10, -10, +10, -10) "
        "between neighboring cells, but the computer will calculate the difference between cell 1 and cell 3 and mistakenly think the pressure is perfectly flat! "
        "To prevent this, the code staggers the variables:"
    )

    add_bullet("Pressure (p): ", "Stored right in the center of the cell [j, i]. Array size is (Ny, Nx).")
    add_bullet("Horizontal Velocity (u): ", "Stored on the left and right vertical edges of the cell. Array size is (Ny, Nx + 1).")
    add_bullet("Vertical Velocity (v): ", "Stored on the bottom and top horizontal edges of the cell. Array size is (Ny + 1, Nx).")

    add_heading_2("Key Class in grid.py:")
    add_bullet("MACGrid: ", "Initializes the dimensions (Lx, Ly), numbers of cells (Nx, Ny), and spacing (dx, dy). Pre-calculates 2D coordinate arrays (X_c, Y_c) so other files can look up positions instantly.")
    add_bullet("to_cell_centers(u, v): ", "Because u and v live on edges, this helper averages neighboring edges to find the exact speed in the center of the box for drawing on screen.")
    add_bullet("compute_vorticity(u, v): ", "Calculates fluid swirl (du/dy - dv/dx). Positive numbers mean spinning counter-clockwise; negative numbers mean clockwise.")

    # --- Section 3: solver/ns_solver.py ---
    add_heading_1("3. The Physics Orchestrator (solver/ns_solver.py)")
    doc.add_paragraph(
        "This file is the conductor of the physics orchestra. Its main class, NavierStokesSolver, controls what happens during each tick of time. "
        "The core method is step(), which performs Chorin's famous 4-step projection algorithm:"
    )

    add_heading_2("Code Breakdown of step():")
    add_bullet("1. Adaptive dt (compute_adaptive_dt): ", 
               "Before moving anything, the code checks how fast the fastest air particle is moving. If air is flying at top speed, it shrinks dt (time step) so no particle can jump over an entire grid cell in one tick (the CFL rule). This prevents the simulation from crashing.")
    
    add_bullet("2. Momentum Advection (compute_advection_u/v): ", 
               "Calculates how existing velocity drifts along with the wind.")

    add_bullet("3. Viscous Friction (compute_diffusion_u/v): ", 
               "Calculates how viscosity (1/Re) smooths out differences between adjacent fast and slow layers of fluid.")

    add_bullet("4. Intermediate Predictor (u*, v*): ", 
               "Updates velocity: u_star = u + dt * (advection + diffusion). This is where the air wants to go before walls and pressure stop it.")

    add_bullet("5. Wall Collision (apply_brinkman_penalization): ", 
               "Applies: u_star /= (1.0 + chi * dt / eta). Where the solid wing exists (chi > 0), the velocity is instantly divided by a huge number, halting the air at the wing surface.")

    add_bullet("6. Pressure Poisson RHS: ", 
               "Calculates div_star = du*/dx + dv*/dy. If div_star > 0, air is expanding; if < 0, air is squishing. The right-hand side (rhs) for pressure is div_star / dt.")

    add_bullet("7. Pressure Solve: ", 
               "Calls the fast spectral solver to find pressure p: self.p = self.poisson_solver.solve(rhs).")

    add_bullet("8. Velocity Correction (project_velocities): ", 
               "Subtracts the pressure gradient from u* and v*: u = u_star - dt * (dp/dx). The resulting velocity field is completely divergence-free (no squishing).")

    # --- Section 4: Numba Acceleration & Advection/Diffusion ---
    add_heading_1("4. The Math Accelerators (advection.py & diffusion.py)")
    doc.add_paragraph(
        "In Python, running nested 'for' loops over 20,000 cells would take 100 milliseconds per step—too slow for a live web game. "
        "Notice the line above almost every math function:"
    )
    add_code_snippet("@njit(fastmath=True, cache=True)\ndef compute_advection_u(...)")
    
    doc.add_paragraph(
        "What does @njit mean? It stands for 'No-Python Just-In-Time compilation'. "
        "The library Numba inspects the Python code, completely bypasses Python's slow interpreter, "
        "and compiles the math loops directly into native machine assembly code (identical to optimized C or Fortran). "
        "This makes the loops run 50 to 100 times faster!"
    )

    add_heading_2("Smart Upwind Blending in advection.py:")
    doc.add_paragraph(
        "When calculating which way air moves, simple central averaging causes artificial waves and ripples. "
        "advection.py uses a donor-cell blend: it looks 'upwind' (where the air just came from) and takes more information "
        "from that direction. This guarantees numerical stability even at higher speeds."
    )

    # --- Section 5: The Spectral Poisson Solver ---
    add_heading_1("5. The Pressure Puzzle (solver/poisson.py)")
    doc.add_paragraph(
        "Calculating pressure is normally the bottleneck of CFD. Every cell's pressure depends on its 4 neighbors simultaneously. "
        "Older programs use iterative loops (like Red-Black SOR) that guess and average hundreds of times. "
        "This program includes a state-of-the-art Spectral Poisson Solver (SpectralPoissonSolver):"
    )

    add_bullet("How It Works: ", 
               "Instead of guessing, it converts the spatial pressure grid into wave frequencies using Discrete Cosine Transforms (DCT) or Fast Fourier Transforms (FFT).")
    add_bullet("The Tridiagonal Shortcut: ", 
               "In frequency space, the 2D grid decouples into simple independent 1D lines. A classic algorithm called the Thomas Algorithm (solve_tridiagonal_batch) solves these lines in a single forward-and-backward pass!")
    add_bullet("The Result: ", 
               "It computes the exact pressure across the entire 192x96 domain in just ~1.2 milliseconds on a single CPU core, keeping divergence at zero to machine precision.")

    # --- Section 6: Geometry & Shapes ---
    add_heading_1("6. Shape Generation & Diagnostics (geometry/)")
    doc.add_paragraph("The geometry module creates the physical obstacles and measures aerodynamic performance:")

    add_bullet("geometry/naca.py (NACA4Airfoil): ", 
               "Takes a 4-digit string like '2412'. Digits 1 & 2 define camber (curvature); digits 3 & 4 define thickness (12%). It calculates upper and lower coordinates using NACA equations and rotates them by angle of attack alpha.")

    add_bullet("geometry/cascade.py (TurbofanCascade): ", 
               "Generates a periodic stack of multiple airfoil blades tilted at stagger angle gamma with spacing (pitch) s/c, modeling a jet engine rotor or stator.")

    add_bullet("geometry/penalization.py: ", 
               "Uses point-in-polygon ray-casting to determine which grid cells fall inside the airfoil or blades. Returns a smooth mask array chi where 1 = solid, 0 = fluid.")

    add_bullet("geometry/diagnostics.py: ", 
               "Measures lift (Cl) and drag (Cd) forces by integrating the penalization force over the body volume. Also computes pressure coefficient (Cp) along the wing surface and blade turning angle.")

    # --- Section 7: Web Server & Frontend ---
    add_heading_1("7. The Web Server & Browser Interface (web/)")
    doc.add_paragraph(
        "The interface is built with two primary files: web/server.py on the backend and web/static/app.js on the frontend."
    )

    add_heading_2("web/server.py (FastAPI Backend):")
    add_bullet("FastAPI Application: ", "Serves the static HTML/CSS files and manages asynchronous WebSocket connections.")
    add_bullet("SimulationManager: ", "Maintains the live simulation state. It runs background time steps in an asyncio task while handling incoming user configuration changes.")
    add_bullet("WebSocket Streaming (websocket_endpoint): ", "Runs two concurrent asynchronous tasks: one listens for incoming button/slider events from the user; the other streams out simulation frames and telemetry at up to 60 FPS.")
    add_bullet("Compact Encoding: ", "Instead of sending thousands of plain text numbers, the server converts the 2D float32 array into raw bytes, base64 encodes it, and sends it as a single string. This keeps network traffic tiny and fast.")

    add_heading_2("web/static/app.js (Browser Frontend):")
    add_bullet("Base64 Decoding: ", "Decodes the raw byte string from Python back into a Float32Array in the browser.")
    add_bullet("Canvas Rendering: ", "Loops over each pixel of the HTML5 <canvas> and applies a colormap (Viridis, Inferno, or CoolWarm) based on normalized scalar values.")
    add_bullet("Smoke Particle Tracer: ", "Maintains 300 virtual particles. In every frame, it reads the local u and v speeds and advects each particle forward. If a particle leaves the screen or enters a wing, it instantly respawns at the inlet!")
    add_bullet("Live HUD Graphs: ", "Updates real-time charts for Lift (Cl), Drag (Cd), and Pressure Distribution (Cp) using Chart.js.")

    # --- Section 8: Summary Table ---
    add_heading_1("8. Code File Quick Reference")
    doc.add_paragraph("A quick lookup cheat sheet for developers and reviewers:")

    table = doc.add_table(rows=9, cols=3)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False

    t_headers = ["File Name", "Primary Class / Function", "Role in System"]
    for i, h in enumerate(t_headers):
        cell = table.cell(0, i)
        cell.paragraphs[0].text = h
        cell.paragraphs[0].runs[0].bold = True
        cell.paragraphs[0].runs[0].font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        set_cell_background(cell, "1E3A8A")
        set_cell_margins(cell, top=80, bottom=80, left=100, right=100)

    rows_info = [
        ("solver/grid.py", "MACGrid", "Manages cell coordinates, staggered faces, divergence, and vorticity."),
        ("solver/ns_solver.py", "NavierStokesSolver", "Coordinates the 4-step Chorin projection cycle and adaptive time steps."),
        ("solver/advection.py", "compute_advection_u/v", "Numba @njit upwind momentum transport calculation."),
        ("solver/diffusion.py", "compute_diffusion_u/v", "Numba @njit viscous friction calculation."),
        ("solver/poisson.py", "SpectralPoissonSolver", "Lightning-fast FFT / DCT direct pressure solver."),
        ("geometry/naca.py", "NACA4Airfoil", "Generates coordinates for NASA 4-digit airfoil profiles."),
        ("geometry/penalization.py", "compute_polygon_mask", "Builds solid obstacle mask via point-in-polygon tests."),
        ("web/server.py", "SimulationManager / ws", "FastAPI server and high-speed WebSocket telemetry streamer.")
    ]

    widths = [Inches(1.8), Inches(2.2), Inches(2.9)]
    for r_idx, r_data in enumerate(rows_info, start=1):
        for c_idx, val in enumerate(r_data):
            cell = table.cell(r_idx, c_idx)
            cell.width = widths[c_idx]
            cell.paragraphs[0].text = val
            cell.paragraphs[0].paragraph_format.line_spacing = 1.15
            cell.paragraphs[0].paragraph_format.space_after = Pt(2)
            bg = "F8FAFC" if r_idx % 2 == 1 else "FFFFFF"
            set_cell_background(cell, bg)
            set_cell_margins(cell, top=70, bottom=70, left=90, right=90)

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
            self.drawString(54, 750, "2D Navier-Stokes CFD Simulator — Code Architecture Guide")
            self.setStrokeColor(colors.HexColor("#E2E8F0"))
            self.setLineWidth(0.5)
            self.line(54, 742, 558, 742)
            
        # Footer
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(558, 36, page_str)
        self.drawString(54, 36, "LAUC Sem 1 & 2 FAP — Code & Implementation Walkthrough")
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
        fontSize=13.5,
        leading=17,
        textColor=colors.HexColor("#1E3A8A"),
        spaceBefore=12,
        spaceAfter=5,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'Heading2_Custom',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=14.5,
        textColor=colors.HexColor("#2563EB"),
        spaceBefore=9,
        spaceAfter=3,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'Body_Custom',
        parent=styles['BodyText'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13.5,
        textColor=colors.HexColor("#1F2937"),
        spaceAfter=5
    )

    bullet_style = ParagraphStyle(
        'Bullet_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#374151"),
        leftIndent=14,
        firstLineIndent=-10,
        spaceAfter=3.5
    )

    code_style = ParagraphStyle(
        'Code_Snippet',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=8.5,
        leading=11.5,
        textColor=colors.HexColor("#1E293B"),
        leftIndent=15,
        spaceBefore=3,
        spaceAfter=4
    )

    callout_style = ParagraphStyle(
        'Callout_Text',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#1E293B")
    )
    
    callout_title = ParagraphStyle(
        'Callout_Title',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#1E3A8A"),
        spaceAfter=2
    )

    table_header_style = ParagraphStyle(
        'TableHeader',
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.white
    )

    table_cell_style = ParagraphStyle(
        'TableCell',
        fontName='Helvetica',
        fontSize=8,
        leading=10.5,
        textColor=colors.HexColor("#1F2937")
    )

    story = []

    # Title
    story.append(Paragraph("The Code Behind the Simulator", title_style))
    story.append(Paragraph("A Simple English Developer & Code Architecture Guide", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#3B82F6"), spaceAfter=10))

    # Callout
    callout_content = [
        [Paragraph("<b>★ ABOUT THIS CODE WALKTHROUGH</b>", callout_title)],
        [Paragraph(
            "This guide explains exactly how the code works under the hood: how Python math functions, "
            "the Numba compiler, the FastAPI web server, and browser JavaScript connect together to simulate fluid flow in real time.",
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
    story.append(Spacer(1, 8))

    # Section 1
    story.append(Paragraph("1. The Big Picture: How Data Flows Through the Code", h1_style))
    story.append(Paragraph("Follow what happens when a user moves a slider on the webpage:", body_style))
    story.append(Paragraph("• <b>1. Browser Event:</b> You drag a slider on <code>index.html</code>. <code>app.js</code> catches this and sends a JSON message over a live WebSocket.", bullet_style))
    story.append(Paragraph("• <b>2. Server Dispatch:</b> <code>server.py</code> receives the JSON in <code>websocket_endpoint()</code> and updates <code>SimulationManager</code>.", bullet_style))
    story.append(Paragraph("• <b>3. Wing Geometry:</b> <code>geometry/naca.py</code> calculates new wing coordinates, and <code>geometry/penalization.py</code> builds a 2D solid obstacle mask.", bullet_style))
    story.append(Paragraph("• <b>4. Physics Step:</b> <code>solver/ns_solver.py</code> runs one time step. It calls <code>advection.py</code>, <code>diffusion.py</code>, and <code>poisson.py</code>. Thanks to Numba's <code>@njit</code>, these run in pure machine code at hardware speed.", bullet_style))
    story.append(Paragraph("• <b>5. Byte Streaming:</b> <code>server.py</code> encodes the fluid speeds as a base64 byte stream and sends it back across the WebSocket.", bullet_style))
    story.append(Paragraph("• <b>6. Canvas Drawing:</b> <code>app.js</code> unpacks the bytes, colors each pixel on the HTML5 canvas, and nudges 300 virtual smoke particles forward!", bullet_style))

    # Section 2
    story.append(Paragraph("2. The Grid System (solver/grid.py)", h1_style))
    story.append(Paragraph(
        "To simulate air, the domain is split into a grid of tiny boxes. "
        "However, this code uses a special layout called a <b>Marker-and-Cell (MAC) Staggered Grid</b>.",
        body_style
    ))
    story.append(Paragraph("Why Stagger Variables?", h2_style))
    story.append(Paragraph(
        "If speed (u, v) and pressure (p) were stored at the exact same point, a computer bug called 'checkerboard decoupling' occurs: "
        "pressure can violently swing (+10, -10, +10) across adjacent cells, but central differencing will mistakenly calculate zero gradient! "
        "The MAC grid solves this permanently by staggering where values live:",
        body_style
    ))
    story.append(Paragraph("• <b>Pressure (p):</b> Stored in cell centers <code>[j, i]</code>. Shape: <code>(ny, nx)</code>.", bullet_style))
    story.append(Paragraph("• <b>Horizontal Speed (u):</b> Stored on vertical cell faces <code>[j, i+1/2]</code>. Shape: <code>(ny, nx + 1)</code>.", bullet_style))
    story.append(Paragraph("• <b>Vertical Speed (v):</b> Stored on horizontal cell faces <code>[j+1/2, i]</code>. Shape: <code>(ny + 1, nx)</code>.", bullet_style))
    story.append(Paragraph("• <b>Key Helpers:</b> <code>to_cell_centers()</code> averages velocities to cell centers for display; <code>compute_vorticity()</code> calculates local fluid spin.", bullet_style))

    # Section 3
    story.append(Paragraph("3. The Physics Orchestrator (solver/ns_solver.py)", h1_style))
    story.append(Paragraph("The central class <code>NavierStokesSolver</code> coordinates Chorin's 4-step projection algorithm inside its <code>step()</code> method:", body_style))
    story.append(Paragraph("• <b>1. Adaptive Time Step (compute_adaptive_dt):</b> Checks maximum flow speed and shrinks <code>dt</code> so particles never skip over a grid cell (CFL stability condition).", bullet_style))
    story.append(Paragraph("• <b>2. Momentum Advection:</b> Calls <code>compute_advection_u/v</code> to drift momentum along velocity vectors.", bullet_style))
    story.append(Paragraph("• <b>3. Viscous Friction:</b> Calls <code>compute_diffusion_u/v</code> to simulate fluid shear friction.", bullet_style))
    story.append(Paragraph("• <b>4. Predictor Velocity:</b> Computes intermediate velocities: <code>u* = u + dt*(advection + diffusion)</code>.", bullet_style))
    story.append(Paragraph("• <b>5. Solid Obstacle Brake (Brinkman Penalization):</b> Divides <code>u*</code> and <code>v*</code> by <code>(1 + chi*dt/eta)</code>. Inside solid wings (<code>chi=1</code>), speed drops to zero.", bullet_style))
    story.append(Paragraph("• <b>6. Pressure Poisson Solve:</b> Solves <code>Laplacian(p) = div(u*)/dt</code> using fast spectral transforms.", bullet_style))
    story.append(Paragraph("• <b>7. Velocity Correction:</b> Updates <code>u = u* - dt*(dp/dx)</code> and <code>v = v* - dt*(dp/dy)</code>, producing a completely divergence-free flow.", bullet_style))

    # Section 4
    story.append(Paragraph("4. The Math Accelerators (advection.py & diffusion.py)", h1_style))
    story.append(Paragraph("In normal Python, looping over 20,000 grid cells takes 100+ ms per step. To fix this, every math function uses Numba:", body_style))
    story.append(Paragraph("<code>@njit(fastmath=True, cache=True)</code>", code_style))
    story.append(Paragraph(
        "Numba compiles these Python loops into raw machine assembly code on startup, delivering C/C++ execution speeds. "
        "In <code>advection.py</code>, a <i>donor-cell upwind blend</i> looks 'upwind' to avoid numerical instability ripples. "
        "In <code>diffusion.py</code>, second-order central differencing smoothly diffuses momentum.",
        body_style
    ))

    # Section 5
    story.append(Paragraph("5. The Pressure Puzzle (solver/poisson.py)", h1_style))
    story.append(Paragraph(
        "Calculating pressure across thousands of interacting cells is typically the slowest part of CFD. "
        "Older software guesses iteratively hundreds of times (SOR). This framework uses a <b>Direct Spectral Poisson Solver</b>:",
        body_style
    ))
    story.append(Paragraph("• <b>Spectral Transformation:</b> Converts the 2D grid into wave frequencies using Discrete Cosine Transforms (DCT-II) for solid walls or Fast Fourier Transforms (FFT) for periodic cascades.", bullet_style))
    story.append(Paragraph("• <b>Tridiagonal Solve:</b> In frequency space, the 2D problem breaks down into independent 1D strings, solved in a single sweep using the Thomas algorithm (<code>solve_tridiagonal_batch</code>).", bullet_style))
    story.append(Paragraph("• <b>Result:</b> Machine-precision divergence-free flow solved in ~1.2 ms on a single CPU core!", bullet_style))

    # Section 6
    story.append(Paragraph("6. Geometry & Shape Generators (geometry/)", h1_style))
    story.append(Paragraph("• <b>geometry/naca.py:</b> Generates coordinates for NASA 4-digit airfoils (e.g., NACA 0012, 2412) with camber and thickness equations, rotated by angle of attack.", bullet_style))
    story.append(Paragraph("• <b>geometry/cascade.py:</b> Stacks multiple airfoil blades at stagger angles and spacing (pitch) to simulate jet engine turbofan rotors.", bullet_style))
    story.append(Paragraph("• <b>geometry/penalization.py:</b> Uses point-in-polygon ray casting to create a solid mask (1 inside, 0 outside).", bullet_style))
    story.append(Paragraph("• <b>geometry/diagnostics.py:</b> Integrates surface pressure and volume forces to compute lift (Cl), drag (Cd), and blade turning angle.", bullet_style))

    # Section 7
    story.append(Paragraph("7. The Web Server & Browser Interface (web/)", h1_style))
    story.append(Paragraph("• <b>web/server.py (FastAPI):</b> Serves HTML files and manages non-blocking WebSocket streams at up to 60 FPS. Converts fluid fields into compact base64 byte streams for ultra-fast network transfer.", bullet_style))
    story.append(Paragraph("• <b>web/static/app.js (Browser):</b> Unpacks the base64 bytes into a Float32Array, maps numbers to colors (Viridis/Inferno/CoolWarm), advects 300 smoke streakline particles, and draws real-time aerodynamic force HUD graphs.", bullet_style))

    # Section 8
    story.append(Paragraph("8. Code Quick Reference Table", h1_style))
    table_data = [
        [Paragraph("<b>File Name</b>", table_header_style), Paragraph("<b>Primary Class / Function</b>", table_header_style), Paragraph("<b>Role in System</b>", table_header_style)],
        [Paragraph("<b>solver/grid.py</b>", table_cell_style), Paragraph("<code>MACGrid</code>", table_cell_style), Paragraph("Coordinates, staggered faces, divergence & vorticity.", table_cell_style)],
        [Paragraph("<b>solver/ns_solver.py</b>", table_cell_style), Paragraph("<code>NavierStokesSolver</code>", table_cell_style), Paragraph("Chorin 4-step loop orchestrator & adaptive dt.", table_cell_style)],
        [Paragraph("<b>solver/advection.py</b>", table_cell_style), Paragraph("<code>compute_advection_u/v</code>", table_cell_style), Paragraph("Numba @njit upwind momentum transport.", table_cell_style)],
        [Paragraph("<b>solver/diffusion.py</b>", table_cell_style), Paragraph("<code>compute_diffusion_u/v</code>", table_cell_style), Paragraph("Numba @njit viscous friction calculation.", table_cell_style)],
        [Paragraph("<b>solver/poisson.py</b>", table_cell_style), Paragraph("<code>SpectralPoissonSolver</code>", table_cell_style), Paragraph("High-speed FFT/DCT direct pressure solver.", table_cell_style)],
        [Paragraph("<b>geometry/naca.py</b>", table_cell_style), Paragraph("<code>NACA4Airfoil</code>", table_cell_style), Paragraph("Airfoil polygon generator from 4-digit code.", table_cell_style)],
        [Paragraph("<b>web/server.py</b>", table_cell_style), Paragraph("<code>SimulationManager</code>", table_cell_style), Paragraph("FastAPI server & WebSocket byte streamer.", table_cell_style)]
    ]
    t_ref = Table(table_data, colWidths=[110, 164, 230])
    t_ref.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor("#F8FAFC"), colors.white]),
    ]))
    story.append(t_ref)

    # Build PDF
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Successfully generated PDF at: {filename}")


if __name__ == "__main__":
    create_docx(DOCX_PATH)
    create_pdf(PDF_PATH)
    
    # Also copy to root directory for easy access
    import shutil
    shutil.copy2(DOCX_PATH, ROOT_DOCX)
    shutil.copy2(PDF_PATH, ROOT_PDF)
    print("Copied files to root directory.")
