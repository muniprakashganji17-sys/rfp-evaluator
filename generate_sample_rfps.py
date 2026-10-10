"""Generate four fictional supplier RFP PDFs (no real data).
Procurement request: Supplier Portal & Procurement Workflow Platform for Meridian Manufacturing Ltd.
Usage: python scripts/generate_sample_rfps.py"""
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

OUT = Path(__file__).resolve().parent.parent / "sample_rfps"
OUT.mkdir(exist_ok=True)
ss = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=ss["Heading1"], fontSize=15, spaceAfter=6)
H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontSize=12, spaceBefore=8, spaceAfter=3)
BODY = ParagraphStyle("B", parent=ss["Normal"], fontSize=10, leading=13.5, spaceAfter=4)

SUPPLIERS = {
"Apex_Systems": dict(
 name="Apex Systems", tagline="Cloud-native engineering for regulated enterprises",
 summary="Meridian Manufacturing Ltd requires a Supplier Portal and Procurement Workflow Platform (RFP-2026-017) to onboard suppliers, manage sourcing events and automate approvals. Apex Systems proposes a cloud-native platform built on a microservice architecture running on Kubernetes across two cloud regions, giving high availability and horizontal scalability. We understand that Meridian needs tight ERP integration and strong controls over supplier data.",
 solution=["<b>Architecture:</b> An API gateway fronts independent microservices for onboarding, sourcing, contracts and approvals. Prebuilt integration connectors exist for SAP S/4HANA and Oracle ERP, with SSO through SAML 2.0 and OIDC.",
  "<b>Scalability:</b> The platform was load tested to 5,000 concurrent users with response times under 800 ms. Autoscaling policies and a documented high availability design (99.95% target) are included in Appendix A.",
  "<b>Approach:</b> Delivery follows six phases from discovery to hypercare, with an integration test environment mirroring Meridian's ERP landscape."],
 timeline=[("Discovery & design","4 weeks","Signed architecture"),("Core build","10 weeks","Portal + workflow beta"),("ERP integration","6 weeks","SAP connector live"),("Testing & UAT","4 weeks","UAT sign-off"),("Go-live","2 weeks","Production release"),("Hypercare","2 weeks","Handover")],
 team="Nine specialists: a delivery manager, solution architect, four engineers, a security engineer and a QA lead. Total duration is 28 weeks with go-live in week 28. A risk register is reviewed fortnightly.",
 price=[("Implementation (fixed price)","USD 412,000"),("Annual licence (per year)","USD 96,000"),("Hypercare & training","USD 28,000"),("Total cost, year 1","USD 536,000")],
 assumptions="Assumes up to 300 suppliers at launch, two ERP connectors, and Meridian providing a UAT team. Change requests are charged at USD 1,100 per day. Payment in four milestones.",
 security=["Apex holds ISO 27001 and SOC 2 Type II certifications, renewed annually.","Data is encrypted at rest (AES-256) and in transit (TLS 1.3). MFA and role-based access control (RBAC) are enforced for all users.","Immutable audit logs are retained for seven years under a documented data retention policy. An independent penetration test and continuous vulnerability scanning are performed annually. A GDPR data processing agreement is provided."],
 risks="Key risks are ERP data quality and UAT availability; both are mitigated through early data profiling and a named Meridian product owner.",
 support="Support desk operates 8x5 (business hours) with a 4-hour SLA for priority 1 incidents. Apex has delivered two similar procurement portals in the last four years.",
 refs="One reference client is available on request; contact details are not included in this response."),
"BrightPath_Tech": dict(
 name="BrightPath Tech", tagline="Fast, affordable procurement software",
 summary="BrightPath Tech offers a ready-made SaaS procurement portal that Meridian can adopt quickly. We understand that Meridian wants low cost and a short timeline. Our standard product covers supplier onboarding and simple approval workflows.",
 solution=["<b>Solution:</b> Our multi-tenant SaaS product provides a standard API and a supplier portal. ERP integration is handled through CSV import and export; a native ERP connector is planned for a future release.",
  "<b>Approach:</b> Meridian configures the standard workflow templates with our help. Customisation beyond configuration is not included."],
 timeline=[("Setup","2 weeks","Tenant ready"),("Configuration","8 weeks","Workflows configured"),("Go-live","4 weeks","Production")],
 team="Delivery is led by a project manager supported by two configuration consultants. No separate risk plan is included.",
 price=[("Fixed price implementation","USD 168,000"),("Annual licence (per year)","USD 42,000"),("Total cost, year 1","USD 210,000")],
 assumptions="Price is fixed. Assumes standard workflows only. Payment 50% at signing and 50% at go-live.",
 security=["BrightPath follows industry-standard security practices and encrypts customer data.","Further security documentation is available on request."],
 risks="Risks are not separately assessed in this response.",
 support="Email support during business hours. BrightPath was founded in 2022 and has completed one similar project.",
 refs="No references are available at this time."),
"NexaWorks": dict(
 name="NexaWorks", tagline="Predictable delivery, dependable support",
 summary="NexaWorks proposes a configurable procurement platform delivered through a structured, milestone-driven programme. We understand that Meridian needs predictable delivery, clear ownership and smooth adoption by 300 suppliers across eleven plants.",
 solution=["<b>Architecture:</b> A modular platform with a documented REST API. Integration with SAP is delivered through a certified middleware adapter; SSO is supported through SAML.",
  "<b>Scalability:</b> The platform supports 1,500 concurrent users in production environments today."],
 timeline=[("Mobilise","2 weeks","Charter, RACI, steering committee"),("Design sprint block","4 weeks","Signed-off process design"),("Build sprints 1-4","8 weeks","Fortnightly demos"),("Integration & data migration","4 weeks","SAP adapter live"),("UAT & training","3 weeks","UAT sign-off, trained super-users"),("Go-live & stabilise","1 week","Production, go-live checklist")],
 team="Eleven named roles including a programme director, delivery lead, two business analysts, four engineers, a change and training lead, a QA lead and a customer success manager. A RACI matrix and weekly steering committee are included. The risk register lists twelve risks with owners and mitigations (for example data migration, supplier adoption and key-person dependency). Staffing is fixed for the full 22-week programme.",
 price=[("Implementation (fixed price)","USD 318,000"),("Contingency (15%, released only with approval)","USD 47,700"),("Annual licence (per year)","USD 78,000"),("Total cost, year 1","USD 443,700"),("Five-year TCO estimate","USD 755,700")],
 assumptions="Assumes 300 suppliers, one ERP adapter and standard reporting. Payment is tied to six milestones. A 5% discount applies if a three-year licence is signed.",
 security=["NexaWorks is ISO 27001 certified. SOC 2 Type II is in progress, expected next year.","Data is encrypted at rest and in transit, MFA and RBAC are supported, and audit logs are available to Meridian administrators. GDPR obligations are covered in the data processing agreement."],
 risks="Residual risks relate to supplier adoption and data migration quality; mitigations are in the risk register.",
 support="A 24x7 support desk with a 1-hour SLA for priority 1 incidents, a defined escalation path and a dedicated customer success manager. NexaWorks has delivered six similar projects over eight years.",
 refs="Three reference clients (manufacturing and logistics) are listed with contact names and project summaries."),
"Orbit_Digital": dict(
 name="Orbit Digital", tagline="Fifteen years of procurement transformation",
 summary="Orbit Digital proposes a procurement platform backed by fifteen years of experience delivering supplier management programmes for large manufacturers. We understand that Meridian wants a trusted partner with a proven record.",
 solution=["<b>Solution:</b> A configurable portal with workflow, contract repository and supplier scorecards. We can connect to the ERP; integration details will be finalised during discovery.",
  "<b>Approach:</b> The technical design will be agreed with Meridian after contract signature."],
 timeline=[("Discovery","4 weeks","Requirements"),("Build","12 weeks","Release candidate"),("Rollout","8 weeks","Go-live")],
 team="Team composition will be confirmed at project start. The overall duration is 24 weeks.",
 price=[("Implementation (fixed price)","USD 355,000"),("Annual licence (per year)","USD 70,000"),("Total cost, year 1","USD 425,000")],
 assumptions="Assumes standard integration scope. Anything beyond this is handled as a change request.",
 security=["Orbit Digital holds SOC 2 Type II certification. Data is encrypted and audit logging is enabled.","Privacy practices follow GDPR; full details are in our trust centre."],
 risks="A formal risk register will be provided after discovery.",
 support="A 24x7 support desk with SLA tiers and an escalation process, plus customer success managers. Orbit has worked with more than 40 clients over 15 years, including twelve similar procurement projects.",
 refs="Five reference clients and three case study summaries are attached, including two Fortune 500 manufacturers."),
}


def build(key, d):
    doc = SimpleDocTemplate(str(OUT / f"{key}_RFP_Response.pdf"), pagesize=letter,
                            leftMargin=0.9*inch, rightMargin=0.9*inch, topMargin=0.8*inch, bottomMargin=0.8*inch,
                            title=f"{d['name']} - RFP Response", author=d["name"])
    def tbl(rows, head, widths):
        t = Table([head] + [list(r) for r in rows], colWidths=widths)
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E5E7EB")),
                               ("GRID", (0, 0), (-1, -1), 0.4, colors.grey), ("FONTSIZE", (0, 0), (-1, -1), 9),
                               ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        return t
    s = [Paragraph(f"{d['name']} - Response to RFP-2026-017", H1),
         Paragraph(f"<i>{d['tagline']}</i> | Fictional document for classroom use", BODY),
         Paragraph("1. Executive Summary and Understanding of the Requirement", H2), Paragraph(d["summary"], BODY),
         Paragraph("2. Proposed Solution and Implementation Approach", H2)]
    s += [Paragraph(p, BODY) for p in d["solution"]]
    s += [Paragraph("3. Timeline, Team Structure and Milestones", H2),
          tbl(d["timeline"], ["Phase", "Duration", "Milestone"], [2.4*inch, 1.2*inch, 2.9*inch]), Spacer(1, 6),
          Paragraph(d["team"], BODY),
          PageBreak(), Paragraph("4. Price Table and Assumptions", H2),
          tbl(d["price"], ["Item", "Amount"], [4.2*inch, 2.3*inch]), Spacer(1, 6),
          Paragraph("<b>Assumptions:</b> " + d["assumptions"], BODY),
          Paragraph("5. Security, Compliance and Risk Controls", H2)]
    s += [Paragraph(p, BODY) for p in d["security"]] + [Paragraph("<b>Risk management:</b> " + d["risks"], BODY)]
    s += [Paragraph("6. Support Model, Experience and References", H2), Paragraph(d["support"], BODY),
          Paragraph("<b>References:</b> " + d["refs"], BODY)]
    doc.build(s)


if __name__ == "__main__":
    for k, d in SUPPLIERS.items():
        build(k, d)
        print("created", k)
