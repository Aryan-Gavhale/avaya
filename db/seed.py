"""Demo content: Anvaya Dental Care, Pune.

Run with `python app.py seed` (or `python app.py reset` to start clean). Every
row written here is editable in the admin panel afterwards, including the page
sections, so the seed is a starting point rather than a fixture the code needs.

Photographs are referenced by URL rather than downloaded, so the seed works on a
machine with no write-heavy media folder. Real practices replace them in the
media library, or import their own Google Place photos.
"""

from __future__ import annotations

from datetime import date, timedelta

from core import db, settings
from core.util import add_months, dump_json, ref_code

U = "https://images.unsplash.com/photo-"
Q = "?auto=format&fit=crop&w=1600&q=80"

PHOTOS = {
    "surgery":    (U + "1629909613654-28e377c37b09" + Q, "A treatment room at Anvaya Dental Care with the chair reclined and instruments laid out"),
    "interior":   (U + "1629909615184-74f495363b67" + Q, "The main surgery seen from the doorway, two chairs and daylight from the street windows"),
    "twin":       (U + "1445527815219-ecbfec67492e" + Q, "Two treatment chairs beside a window wall in the Baner clinic"),
    "chairside":  (U + "1598256989800-fe5f95da9787" + Q, "A dental chair with the overhead light angled away, ready for the next patient"),
    "treating":   (U + "1606811841689-23dfddce3e95" + Q, "A dentist working chairside with an assistant while the patient watches the screen"),
    "xray":       (U + "1588776814546-1ffcf47267a5" + Q, "A clinician reading a set of dental X-rays on the light wall"),
    "aligner":    (U + "1609840114035-3c981b782dfe" + Q, "A teenager holding up a clear aligner tray before fitting it"),
    "scans":      (U + "1666214280557-f1b5022eb634" + Q, "Two clinicians discussing a scan on the wall monitor before treatment planning"),
    "consult":    (U + "1631217868264-e5b90bb7e133" + Q, "A dentist talking a patient through her treatment plan across the consulting desk"),
    "instrument": (U + "1576091160550-2173dba999ef" + Q, "Sterilised instruments laid out on a tray before a procedure"),
    "desk":       (U + "1517245386807-bb43f82c33c4" + Q, "Reception going through a written estimate with a patient at the front desk"),
    "dr_aditi":   (U + "1559839734-2b71ea197ec2" + Q, "Dr Aditi Deshmukh, founder and prosthodontist"),
    "dr_rohan":   (U + "1612349317150-e413f6a5b16d" + Q, "Dr Rohan Kulkarni, endodontist"),
    "dr_sneha":   (U + "1594824476967-48c8b964273f" + Q, "Dr Sneha Iyer, orthodontist"),
    "dr_vikram":  (U + "1622253692010-333f2da6031d" + Q, "Dr Vikram Rane, oral and maxillofacial surgeon"),
}

CATEGORIES = [
    ("Preventive", "Cleaning, check-ups and everything that stops treatment being needed later."),
    ("Restorative", "Rebuilding a tooth that is damaged, decayed or missing."),
    ("Orthodontics", "Straightening, with braces or clear aligners."),
    ("Cosmetic", "Changing how teeth look, in a way that still lasts."),
    ("Surgical", "Extractions, implants and the day-care surgical work."),
    ("Children", "First visits, sealants and habit correction, in their own room."),
]

SERVICES = [
    # name, category, icon, summary, price_from, price_to, mins, sittings, emi, featured, photo, body
    ("Dental implants", "Surgical", "implant",
     "A titanium root and a zirconia crown, planned on a CBCT scan before anything is touched.",
     28000, 55000, 90, "2 visits, 3-4 months apart", 1, 1, "surgery",
     "An implant replaces the root of a missing tooth, so the bone around it keeps its shape "
     "instead of shrinking the way it does under a bridge or denture.\n\n"
     "We plan every case on a CBCT scan first, which tells us the bone height and where the "
     "nerve runs. You see the plan on screen before we start. Placement takes about ninety "
     "minutes under local anaesthetic, and the crown goes on once the implant has integrated, "
     "usually three to four months later.\n\n"
     "The quote you get is per tooth and includes the scan, the fixture, the abutment and the "
     "crown. Bone grafting, if the scan shows you need it, is quoted separately and never "
     "added after the fact."),
    ("Root canal treatment", "Restorative", "root",
     "Single-sitting endodontics with rotary files and an apex locator, done under magnification.",
     6500, 12000, 60, "Usually 1 visit", 0, 1, "treating",
     "Root canal treatment cleans the infected pulp out of a tooth so the tooth itself can stay "
     "in your mouth. Done properly, it is not the ordeal it is famous for.\n\n"
     "Most of our cases finish in one sitting of about an hour. We work under magnification with "
     "rotary files and an apex locator, which is what keeps the file inside the root rather than "
     "past it. You will need a crown afterwards on back teeth, and we will tell you that at the "
     "start, not once the anaesthetic has worn off."),
    ("Invisible aligners", "Orthodontics", "aligner",
     "Clear trays with a printed plan you can see before you commit, reviewed every six weeks.",
     145000, 220000, 45, "Review every 6 weeks", 1, 1, "aligner",
     "Aligners move teeth with a series of clear trays, each one slightly different from the "
     "last. They come out for meals, which is why adults tend to prefer them to braces.\n\n"
     "We scan your teeth, then show you the simulated end position before you pay for the case. "
     "If the simulation does not achieve what you want, braces may be the honest answer and we "
     "will say so. Cases here typically run twelve to twenty months with a review every six "
     "weeks, and retainers are included for the first year."),
    ("Braces, metal and ceramic", "Orthodontics", "braces",
     "Fixed orthodontics with monthly adjustments and a written plan for the whole course.",
     45000, 85000, 40, "Monthly adjustments", 1, 0, "aligner",
     "Fixed braces still do things aligners cannot, particularly with rotations and bite "
     "correction in growing patients. Metal is the workhorse; ceramic brackets are less visible "
     "and cost a little more.\n\n"
     "The fee covers the whole course, including every adjustment visit and the first set of "
     "retainers. We put the expected duration in writing at the start."),
    ("Full mouth rehabilitation", "Restorative", "rehab",
     "Rebuilding a worn or collapsed bite in staged, quoted phases with nothing hidden.",
     180000, 450000, 120, "Staged over 4-8 months", 1, 1, "scans",
     "When years of wear, grinding or missing teeth have changed how the whole bite meets, "
     "treating one tooth at a time does not hold. A rehabilitation rebuilds the bite as one "
     "plan.\n\n"
     "We stage it: records and diagnosis, then a trial in temporary material you live with for "
     "a few weeks, then the final work. Each phase is quoted separately, so you can stop at the "
     "end of any phase and know exactly where you stand."),
    ("Zirconia crowns and bridges", "Restorative", "crown",
     "Digitally scanned, milled in a Pune lab, seated in two visits.",
     12000, 18000, 60, "2 visits, a week apart", 0, 0, "instrument",
     "A crown covers a tooth that has lost too much structure to survive on a filling. Zirconia "
     "is strong enough for back teeth and layered enough to look right at the front.\n\n"
     "We take a digital scan rather than a tray of impression material, send it to a lab we work "
     "with in Pune, and seat the crown about a week later. The temporary you wear in between is "
     "made to fit properly, not just to fill the gap."),
    ("Teeth whitening", "Cosmetic", "whiten",
     "In-chair whitening with a take-home top-up kit and a shade record before and after.",
     9000, 14000, 75, "1 visit", 0, 1, "chairside",
     "Whitening lifts stain out of enamel. It will not change the colour of a crown or a "
     "filling, and we record your starting shade so the result is measured rather than argued "
     "about.\n\n"
     "One in-chair session takes about seventy-five minutes. Sensitivity for a day or two is "
     "normal and settles. If your teeth are already at the limit of what whitening can do, we "
     "will tell you before you pay."),
    ("Smile design and veneers", "Cosmetic", "veneer",
     "A mock-up you wear before any enamel is touched, then minimal-prep veneers.",
     15000, 25000, 90, "3 visits over 3 weeks", 1, 0, "desk",
     "Veneers are thin facings bonded to the front of the teeth. Because they are irreversible, "
     "we do the design first and the drilling last.\n\n"
     "You get a trial smile in composite, worn for a few days, so you can see the shape and "
     "length in your own face and in your own photographs. Only when you sign that off do we "
     "prepare the teeth. Price is per tooth."),
    ("Scaling and gum care", "Preventive", "clean",
     "Ultrasonic scaling, polishing and a pocket chart so you can see the change next time.",
     1500, 3500, 45, "Every 6 months", 0, 0, "instrument",
     "Bleeding gums are the most common thing we see and the easiest to reverse early. Scaling "
     "removes the hard deposit that brushing cannot.\n\n"
     "We chart pocket depths at every visit, so at the next appointment you can see whether the "
     "gum has improved rather than take our word for it. Deeper cases need root planing, which "
     "we quote separately."),
    ("Wisdom tooth removal", "Surgical", "extract",
     "Day-care surgical extraction with the CBCT read out to you first.",
     5000, 15000, 45, "1 visit", 0, 0, "xray",
     "Not every wisdom tooth needs to come out. When one does, the scan tells us how close the "
     "root sits to the nerve, and we show you that image before booking.\n\n"
     "Most removals are done under local anaesthetic in about forty-five minutes. You get "
     "written after-care and a number to ring the same evening if something worries you."),
    ("Children's dentistry", "Children", "child",
     "First visits, sealants and habit correction, in a room built for small patients.",
     800, 4000, 30, "Every 6 months", 0, 0, "consult",
     "The first visit is a look and a chat, nothing more. Children who meet a dentist before "
     "anything hurts tend to stay comfortable in the chair for life.\n\n"
     "We seal molars as they come through, treat decay in ways that suit their age, and step in "
     "early on thumb-sucking and mouth-breathing where it is starting to change the jaw."),
    ("Dentures, partial and complete", "Restorative", "denture",
     "Conventional and implant-supported dentures, fitted and then adjusted until they work.",
     18000, 65000, 60, "4-5 visits over 6 weeks", 1, 0, "twin",
     "A denture has to work while you eat and talk, not only while you sit still in a chair. "
     "That is a fitting problem more than a manufacturing one.\n\n"
     "We take our time over the records and expect to adjust after you have worn it for a few "
     "days. Where the lower jaw will not hold a denture still, two implants underneath it change "
     "the experience completely, and we will price both options."),
]

DOCTORS = [
    ("Dr Aditi Deshmukh", "Founder and prosthodontist", "MDS Prosthodontics, Govt Dental College Mumbai",
     "A-12847", 18, "Implants, full mouth rehabilitation, smile design", "dr_aditi",
     "Aditi started Anvaya in 2011 after eight years in a hospital prosthodontics unit. She takes "
     "the complex rebuilds and the cases other practices have already tried once. She is the "
     "reason every plan here goes out in writing with the number on it."),
    ("Dr Rohan Kulkarni", "Endodontist", "MDS Conservative Dentistry and Endodontics, Nair Hospital",
     "A-19233", 12, "Root canals, re-treatment, dental trauma", "dr_rohan",
     "Rohan does the root canals other dentists refer out, including the re-treatments where a "
     "first attempt has failed. He works under a microscope and will show you the file lengths on "
     "screen if you want to see them."),
    ("Dr Sneha Iyer", "Orthodontist", "MDS Orthodontics and Dentofacial Orthopaedics, MA Rangoonwala",
     "A-22910", 10, "Clear aligners, fixed braces, early growth guidance", "dr_sneha",
     "Sneha runs the orthodontic list across both clinics. She is careful about promising what "
     "aligners can do, and will recommend braces when they are simply the better tool for your "
     "bite."),
    ("Dr Vikram Rane", "Oral and maxillofacial surgeon", "MDS Oral and Maxillofacial Surgery, Sinhgad",
     "A-20455", 15, "Implant surgery, wisdom teeth, bone grafting", "dr_vikram",
     "Vikram handles the surgical list, from difficult third molars to grafting for implant sites. "
     "Patients tend to remember that he explains the scan before he touches anything."),
]

HOURS_MAIN = {
    "mon": ["09:30", "20:00"], "tue": ["09:30", "20:00"], "wed": ["09:30", "20:00"],
    "thu": ["09:30", "20:00"], "fri": ["09:30", "20:00"], "sat": ["09:30", "18:00"],
    "sun": [],
}
HOURS_BANER = {
    "mon": ["10:00", "19:30"], "tue": ["10:00", "19:30"], "wed": ["10:00", "19:30"],
    "thu": ["10:00", "19:30"], "fri": ["10:00", "19:30"], "sat": ["10:00", "17:00"],
    "sun": [],
}

BRANCHES = [
    ("Law College Road", "1st Floor, Sahyadri House, Law College Road, Erandwane", "Pune", "411004",
     "+91 20 4120 8800", "919000012345", "lawcollege@anvayadental.in", HOURS_MAIN, "interior",
     "Two surgeries, a separate sterilisation room and a CBCT on site. Paid parking in the "
     "building basement, entrance from the lane behind Sahyadri House."),
    ("Baner", "Shop 4, Sun Empire, Baner Road, near Baner Telephone Exchange", "Pune", "411045",
     "+91 20 4120 8811", "919000012346", "baner@anvayadental.in", HOURS_BANER, "twin",
     "Our newer clinic, opened 2019. Three surgeries including a paediatric room, and the "
     "orthodontic list runs here on Tuesdays and Saturdays."),
]

FAQS = [
    ("Do I need an appointment or can I walk in?", "General",
     "Both work, but an appointment means you are seen at the time you were given. Walk-ins are "
     "fitted between booked patients, so the wait depends on the day. Emergencies are always seen."),
    ("Will you tell me the cost before you start?", "Money",
     "Yes, in writing, itemised, before any treatment begins. If the treatment changes once we are "
     "underway, we stop and re-quote rather than adding it to the bill afterwards."),
    ("Is the EMI really no-cost?", "Money",
     "On the six, nine and twelve month plans, yes: you pay the treatment price divided by the "
     "number of months, and nothing more. The longer plans carry interest, and the exact figure is "
     "shown in the calculator before you apply."),
    ("Do you take insurance or CGHS?", "Money",
     "We give you a fully itemised invoice with procedure codes, which most reimbursement schemes "
     "accept. We are not empanelled with CGHS. Cashless corporate plans depend on your insurer, so "
     "ring us with the policy name and we will check."),
    ("How do you sterilise instruments?", "Safety",
     "Every instrument is scrubbed, ultrasonically cleaned, pouched and autoclaved at 134 degrees. "
     "Each cycle is logged and we spore-test weekly. Ask at reception and you can see the log."),
    ("Is a root canal painful?", "Treatment",
     "The procedure itself should not be, because the tooth is fully anaesthetised. Aching for a "
     "day or two afterwards is common and responds to ordinary painkillers. Pain that gets worse "
     "on day three is a reason to ring us, not to wait."),
    ("How long do implants last?", "Treatment",
     "Well-maintained implants routinely last fifteen years or more, and the fixture itself often "
     "far longer. What fails first is usually the gum around it, which is why the six-monthly "
     "review matters more than anything we do on the day."),
    ("Can you see my child, and from what age?", "Children",
     "From the first tooth. The first appointment is a look and a conversation, no treatment, so "
     "the room stops being frightening before anything needs doing."),
    ("What happens if something goes wrong out of hours?", "General",
     "The emergency number on this page reaches a clinician, not a call centre. Out of hours you "
     "will get advice and, if it cannot wait, a slot first thing the next morning."),
    ("Do you offer a second opinion on someone else's plan?", "General",
     "Often. Bring the plan, the estimate and any X-rays. A second opinion consultation is 500 "
     "rupees, waived if you go on to have the treatment with us."),
]

TESTIMONIALS = [
    ("Meghana Joshi", "Implant patient, 2025", 5,
     "I had put off two implants for three years because every place quoted a different number. "
     "Anvaya scanned first, showed me the bone on screen and gave me one page with the total on "
     "it. The final bill was that number, to the rupee.", "Dental implants"),
    ("Sanjay Pardeshi", "Root canal, 2026", 5,
     "Came in at 7pm with a tooth that had kept me up two nights. Dr Kulkarni finished the root "
     "canal in one sitting and I slept properly the same night. He also explained why the crown "
     "was not optional, which I appreciated.", "Root canal treatment"),
    ("Farida Contractor", "Aligners, 2025", 5,
     "The simulation was honest. Dr Iyer told me one tooth would not move as far as I wanted "
     "without a small reshaping, and she was right. Fourteen months and I stopped hiding my "
     "teeth in photographs.", "Invisible aligners"),
    ("Amit Barve", "Full mouth rehabilitation, 2025", 5,
     "Years of grinding had worn everything down. They staged it into three phases, each one "
     "quoted, and I paid over eighteen months on the EMI. I can chew on both sides for the first "
     "time since my thirties.", "Full mouth rehabilitation"),
    ("Priya Raut", "Parent of a patient, 2026", 5,
     "My daughter is seven and terrified of doctors. First visit they did nothing except let her "
     "sit in the chair and hold the mirror. Second visit she let them seal her molars. That is "
     "not luck, that is method.", "Children's dentistry"),
    ("Nikhil Shetty", "Scaling and gum care, 2026", 4,
     "Straightforward cleaning, done well, and the gum chart made it obvious that my bleeding had "
     "halved since the last visit. Parking is the only frustration on Law College Road.",
     "Scaling and gum care"),
]

EMI_PLANS = [
    ("6 months, no cost", "In-house", 6, 0, 0, 0, 15000, 0,
     "No interest and no processing fee. The most popular plan for crowns and root canals."),
    ("9 months, no cost", "In-house", 9, 0, 0, 0, 25000, 0,
     "No interest and no processing fee. Suits single implants and braces."),
    ("12 months, no cost", "In-house", 12, 0, 0, 10, 40000, 0,
     "No interest, no fee, 10 percent paid on the day treatment starts."),
    ("18 months", "In-house", 18, 9.0, 1.0, 10, 75000, 0,
     "9 percent a year on the financed amount, 1 percent processing fee. For rehabilitation and "
     "aligner cases."),
    ("24 months", "In-house", 24, 12.0, 1.5, 15, 150000, 0,
     "12 percent a year with a 15 percent downpayment. Used for the largest treatment plans."),
]

NAV = [
    ("Treatments", "/treatments", "header"),
    ("EMI and payment", "/emi-and-payment", "header"),
    ("Our clinics", "/#locations", "header"),
    ("The team", "/about", "header"),
    ("Contact", "/contact", "header"),
    ("Treatments and fees", "/treatments", "footer"),
    ("EMI and payment", "/emi-and-payment", "footer"),
    ("About the practice", "/about", "footer"),
    ("Contact and directions", "/contact", "footer"),
    ("Dental implants", "/treatments/dental-implants", "footer2"),
    ("Invisible aligners", "/treatments/invisible-aligners", "footer2"),
    ("Root canal treatment", "/treatments/root-canal-treatment", "footer2"),
    ("Children's dentistry", "/treatments/childrens-dentistry", "footer2"),
]

SAMPLE_ENQUIRIES = [
    ("Ketan Mhatre", "+91 98220 41188", "ketan.mhatre@gmail.com", "Dental implants", "Law College Road",
     "Morning (9am - 1pm)", "Lost a lower molar two years ago, want to know if an implant is still "
     "possible.", "new", "high", 0),
    ("Ritika Sharma", "+91 90040 22119", "ritika.sharma@outlook.com", "Invisible aligners", "Baner",
     "Evening (5pm - 9pm)", "Interested in aligners, would like to understand the EMI options first.",
     "contacted", "normal", 2),
    ("Suhas Kale", "+91 98901 77320", "", "Root canal treatment", "Law College Road",
     "Morning (9am - 1pm)", "Tooth pain on the upper right since Sunday, getting worse at night.",
     "booked", "high", 3),
    ("Anjali Nadkarni", "+91 99700 55412", "anjali.n@yahoo.in", "Teeth whitening", "Baner",
     "Afternoon (2pm - 5pm)", "Wedding in November, wondering how far ahead to do the whitening.",
     "contacted", "normal", 5),
    ("Deepak Gaikwad", "+91 88880 12234", "deepak.g@rediffmail.com", "Full mouth rehabilitation",
     "Law College Road", "Morning (9am - 1pm)", "Second opinion on a plan I was given elsewhere, "
     "quoted 5.6 lakh. I have the X-rays.", "treated", "high", 12),
    ("Shalini Rao", "+91 97640 88123", "shalini.rao@gmail.com", "Children's dentistry", "Baner",
     "Afternoon (2pm - 5pm)", "My son is 6 and has a cavity in a back milk tooth.", "closed",
     "normal", 18),
    ("Prakash Jadhav", "+91 91560 33471", "", "Scaling and gum care", "Law College Road",
     "Evening (5pm - 9pm)", "Gums bleed when I brush. Last cleaning was three years ago.", "new",
     "normal", 1),
    ("Nandini Kher", "+91 93710 66234", "nandini.kher@gmail.com", "Braces, metal and ceramic", "Baner",
     "Afternoon (2pm - 5pm)", "Daughter is 13, school dentist said she needs braces.", "lost",
     "low", 26),
]


# ── helpers ─────────────────────────────────────────────────────────────────
def _media(key: str) -> int:
    url, alt = PHOTOS[key]
    existing = db.one("SELECT id FROM media WHERE url = ?", (url,))
    if existing:
        return existing["id"]
    return db.insert("media", {
        "url": url, "alt": alt, "title": key.replace("_", " ").title(),
        "source": "remote", "credit": "Unsplash", "width": 1600, "height": 1067,
        "mime": "image/jpeg",
    })


def _page(slug, title, meta_title, meta_desc, is_home=0, order=0, og=None):
    return db.insert("pages", {
        "slug": slug, "title": title, "meta_title": meta_title,
        "meta_description": meta_desc, "is_home": is_home, "sort_order": order,
        "og_media_id": og, "is_published": 1,
    })


def _section(page_id, order, type_, name, eyebrow="", title="", subtitle="", body="", data=None,
             anchor=""):
    return db.insert("sections", {
        "page_id": page_id, "type": type_, "name": name, "anchor": anchor,
        "eyebrow": eyebrow, "title": title, "subtitle": subtitle, "body": body,
        "data": dump_json(data or {}), "sort_order": order, "is_published": 1,
    })


def _lines(*rows) -> list:
    return list(rows)


# ── seed ────────────────────────────────────────────────────────────────────
def run(force: bool = False) -> None:
    existing = int(db.scalar("SELECT COUNT(*) FROM pages", (), 0))
    if existing and not force:
        print("[seed] pages already exist; nothing written. Use `python app.py reset` to rebuild.")
        return
    if force:
        for table in ("gallery_items", "galleries", "sections", "pages", "services",
                      "service_categories", "doctors", "branches", "faqs", "testimonials",
                      "nav_items", "emi_installments", "payments", "emi_applications",
                      "emi_plans", "enquiry_events", "enquiries", "media", "review_sync_log",
                      "google_reviews_cache", "audit_log"):
            db.execute(f"DELETE FROM {table}")
        print("[seed] cleared existing content")

    settings.ensure_defaults()
    settings.set_many({
        "brand.logo_media_id": None,
        "seo.og_media_id": _media("interior"),
    })

    # ── catalogue ───────────────────────────────────────────────────────────
    cat_ids = {}
    for i, (name, summary) in enumerate(CATEGORIES):
        cat_ids[name] = db.insert("service_categories", {
            "name": name, "slug": name.lower().replace(" ", "-"), "summary": summary,
            "sort_order": i, "is_published": 1,
        })

    service_ids = {}
    for i, row in enumerate(SERVICES):
        (name, cat, icon, summary, pfrom, pto, mins, sittings, emi, feat, photo, body) = row
        slug = (name.lower().replace(",", "").replace("'", "").replace(" and ", " ")
                    .replace(" ", "-"))
        service_ids[name] = db.insert("services", {
            "name": name, "slug": slug, "category_id": cat_ids[cat], "icon": icon,
            "summary": summary, "body": body, "price_from": pfrom, "price_to": pto,
            "duration_min": mins, "sittings": sittings, "media_id": _media(photo),
            "emi_eligible": emi, "is_featured": feat, "sort_order": i, "is_published": 1,
        })

    for i, (name, role, qual, reg, years, spec, photo, bio) in enumerate(DOCTORS):
        db.insert("doctors", {
            "name": name, "role_title": role, "qualification": qual, "reg_no": reg,
            "experience_yr": years, "specialities": spec, "bio": bio,
            "media_id": _media(photo), "sort_order": i, "is_published": 1,
        })

    branch_ids = {}
    for i, (name, addr, city, pin, phone, wa, email, hours, photo, note) in enumerate(BRANCHES):
        branch_ids[name] = db.insert("branches", {
            "name": name, "address": addr, "city": city, "pincode": pin, "phone": phone,
            "whatsapp": wa, "email": email, "hours": dump_json(hours),
            "map_embed": note, "media_id": _media(photo),
            "directions_url": f"https://maps.google.com/?q=Anvaya+Dental+{name.replace(' ', '+')}+Pune",
            "sort_order": i, "is_published": 1,
        })

    for i, (question, category, answer) in enumerate(FAQS):
        db.insert("faqs", {"question": question, "answer": answer, "category": category,
                           "sort_order": i, "is_published": 1})

    for i, (author, role, rating, body, treatment) in enumerate(TESTIMONIALS):
        db.insert("testimonials", {
            "author": author, "author_role": role, "rating": rating, "body": body,
            "treatment": treatment, "source": "manual", "is_featured": 1 if i < 3 else 0,
            "sort_order": i, "is_published": 1,
        })

    for i, (label, url, location) in enumerate(NAV):
        db.insert("nav_items", {"label": label, "url": url, "location": location,
                                "sort_order": i, "is_published": 1})

    for i, row in enumerate(EMI_PLANS):
        (name, provider, tenure, rate, fee, down, minimum, maximum, notes) = row
        db.insert("emi_plans", {
            "name": name, "provider": provider, "tenure_months": tenure, "interest_rate": rate,
            "processing_fee_pct": fee, "downpayment_pct": down, "min_amount": minimum,
            "max_amount": maximum, "notes": notes, "sort_order": i, "is_active": 1,
        })

    # ── gallery ─────────────────────────────────────────────────────────────
    gallery_id = db.insert("galleries", {"name": "Both clinics", "slug": "clinics"})
    gallery_shots = [
        ("interior", "The Law College Road surgery, looking in from the corridor"),
        ("twin", "Baner, where the orthodontic list runs on Tuesdays and Saturdays"),
        ("treating", "Chairside, with the intraoral camera on the screen you can see"),
        ("xray", "Reading a full mouth series before planning"),
        ("instrument", "Pouched and autoclaved, one tray per patient"),
        ("chairside", "Between patients, the room reset and ready"),
        ("scans", "Treatment planning, done together rather than behind a door"),
        ("desk", "The written estimate, gone through line by line at reception"),
    ]
    for i, (key, caption) in enumerate(gallery_shots):
        db.insert("gallery_items", {"gallery_id": gallery_id, "media_id": _media(key),
                                    "caption": caption, "sort_order": i})

    # ── home page ───────────────────────────────────────────────────────────
    home = _page("home", "Anvaya Dental Care, Pune",
                 "Dentist in Pune | Anvaya Dental Care, Law College Road and Baner",
                 settings.get("seo.default_description"), is_home=1, order=0,
                 og=_media("interior"))

    _section(home, 0, "hero", "Opening", eyebrow="Pune, since 2011",
             title="Dentistry that explains itself, then does what it said",
             subtitle="Two clinics on Law College Road and in Baner. Every plan scanned first, "
                      "quoted in writing, and paid over months if that suits you better.",
             data={
                 "media_id": _media("surgery"), "secondary_media_id": _media("treating"),
                 "badge": "Autoclave logs on request",
                 "rating_note": "",
                 "points": _lines({"text": "Written, itemised estimate before treatment starts"},
                                  {"text": "CBCT and intraoral scanning on site"},
                                  {"text": "No-cost EMI from six to twelve months"},
                                  {"text": "Same-day emergency slots kept back every morning"}),
                 "primary_label": "Book an appointment", "primary_url": "#enquiry",
                 "secondary_label": "See treatments and fees", "secondary_url": "/treatments",
             })

    _section(home, 1, "trust", "Assurance strip", data={
        "items": _lines(
            {"title": "Fees in writing", "text": "Itemised before we start, honoured after"},
            {"title": "134 degrees, logged", "text": "Every cycle recorded, spore-tested weekly"},
            {"title": "Scan before opinion", "text": "CBCT and intraoral scanning in-house"},
            {"title": "One clinician throughout", "text": "The dentist who plans it, treats it"},
        )})

    _section(home, 2, "stats", "Numbers", eyebrow="Fifteen years on",
             title="What that adds up to",
             data={"tone": "canvas", "items": _lines(
                 {"value": "24000", "suffix": "+", "label": "patients treated since 2011"},
                 {"value": "4100", "suffix": "", "label": "implants placed and reviewed"},
                 {"value": "15", "suffix": " yrs", "label": "the same founding clinician"},
                 {"value": "98", "suffix": "%", "label": "estimates matched to the final bill"},
             )})

    _section(home, 3, "services", "Treatments", anchor="services", eyebrow="What we do",
             title="Treatments, with the price band on the card",
             subtitle="Bands are what patients actually pay here, not a headline figure. Your "
                      "written estimate lands inside them.",
             data={"mode": "featured", "limit": 6, "show_price": 1,
                   "cta_label": "All treatments and fees", "cta_url": "/treatments"})

    _section(home, 4, "about", "About", eyebrow="How we work",
             title="The consultation is the treatment plan, not a sales call",
             subtitle="You leave the first visit with a scan you have seen, a plan you understood "
                      "and a number you can take away and think about.",
             body="Anvaya started in 2011 in two rooms on Law College Road. The practice has grown "
                  "to two clinics and nine clinicians, and the thing that has not changed is that "
                  "the dentist who plans your treatment is the one who carries it out.\n\n"
                  "We are unusually strict about one thing: nothing gets added to a bill "
                  "mid-treatment. If the tooth turns out to need more than the scan suggested, we "
                  "stop, tell you, and re-quote before continuing.",
             data={"media_id": _media("consult"), "flip": 0, "tone": "light",
                   "points": _lines(
                       {"title": "Diagnosis before opinion",
                        "text": "CBCT, intraoral scan and photographs, read out to you on screen"},
                       {"title": "One page, itemised",
                        "text": "Procedure by procedure, with what is not included stated plainly"},
                       {"title": "Second opinions welcome",
                        "text": "Bring the plan and the X-rays. 500 rupees, waived if you treat here"},
                   ),
                   "cta_label": "Meet the clinicians", "cta_url": "/about"})

    _section(home, 5, "process", "Process", eyebrow="Your first visit",
             title="Four steps, about fifty minutes",
             data={"tone": "light", "items": _lines(
                 {"title": "Records", "text": "Photographs, an intraoral scan and a CBCT if the "
                                              "case needs one. Fifteen minutes."},
                 {"title": "Read-out", "text": "We put the scan on the screen and go through what "
                                               "we can see, tooth by tooth."},
                 {"title": "Options", "text": "Usually two or three, with what each costs and what "
                                              "happens if you do nothing."},
                 {"title": "The page", "text": "An itemised estimate, emailed the same day. No "
                                               "pressure to book on the spot."},
             )})

    _section(home, 6, "gallery", "Gallery", anchor="clinics", eyebrow="Both clinics",
             title="The rooms you will actually sit in",
             subtitle="Photographed on ordinary working days, between patients.",
             data={"gallery_id": gallery_id, "layout": "mosaic", "tone": "light"})

    _section(home, 7, "doctors", "Clinicians", anchor="doctors", eyebrow="Who treats you",
             title="Nine clinicians, four of whom you will meet first",
             subtitle="Registration numbers are on every profile. Ask for a specialist by name "
                      "when you book.",
             data={"limit": 4, "tone": "canvas"})

    # the heading stays source-neutral: the score chip and the disclosure below
    # the quotes are what name Google, and only once a profile is connected
    _section(home, 8, "reviews", "Reviews", anchor="reviews", eyebrow="Reviews",
             title="What patients say afterwards",
             subtitle="Pulled live from our Google Business Profile, not retyped by us.",
             data={"source": "auto", "limit": 6, "show_summary": 1, "tone": "light"})

    _section(home, 9, "emi", "EMI calculator", anchor="emi", eyebrow="Paying for it",
             title="Work out the monthly figure before you come in",
             subtitle="Move the amount, pick a tenure. The six, nine and twelve month plans are "
                      "genuinely no-cost.",
             body="Approval needs a PAN, one address proof and a look at the treatment plan. We "
                  "decide in-house, usually the same day, and nothing is charged for applying.",
             data={"default_amount": 60000, "max_amount": 400000, "tone": "deep",
                   "points": _lines(
                       {"title": "No cost means no cost",
                        "text": "Treatment price divided by the months. No interest, no fee"},
                       {"title": "Decided here",
                        "text": "No third-party lender, no credit-score rejection out of our hands"},
                       {"title": "Stop any time",
                        "text": "Clear the balance early and the remaining instalments close"},
                   )})

    _section(home, 10, "branches", "Locations", anchor="locations", eyebrow="Where we are",
             title="Two clinics, both in west Pune",
             subtitle="Law College Road has the CBCT and the surgical list. Baner has the "
                      "paediatric room.",
             data={"show_map": 1, "tone": "canvas"})

    _section(home, 11, "faq", "FAQ", anchor="faq", eyebrow="Before you ring",
             title="The questions reception is asked most",
             data={"category": "", "limit": 8, "tone": "light"})

    _section(home, 12, "enquiry", "Enquiry form", anchor="enquiry", eyebrow="Book",
             title="Ask for an appointment",
             subtitle="Reception rings back the same working day. Nothing is confirmed until you "
                      "have spoken to a person.",
             data={"show_service": 1, "show_branch": 1, "show_slot": 1, "tone": "light",
                   "side_points": _lines(
                       {"title": "In pain today?",
                        "text": "Ring 020 4120 8800. We keep back emergency slots every morning"},
                       {"title": "Bringing someone else's plan?",
                        "text": "Attach nothing here, just say so and bring the X-rays with you"},
                       {"title": "Prefer WhatsApp?",
                        "text": "Message the clinic number and reception will answer in hours"},
                   )})

    _section(home, 13, "cta", "Closing band", eyebrow="",
             title="Fifteen years, two clinics, one way of working",
             subtitle="Scan first, quote in writing, then treat.",
             data={"media_id": _media("chairside"), "tone": "ink",
                   "primary_label": "Book an appointment", "primary_url": "#enquiry",
                   "secondary_label": "Call 020 4120 8800", "secondary_url": "tel:+912041208800"})

    # ── treatments page ─────────────────────────────────────────────────────
    treatments = _page("treatments", "Treatments and fees",
                       "Dental treatments and fees in Pune | Anvaya Dental Care",
                       "Every treatment we offer with the price band patients actually pay, plus "
                       "what each estimate includes.", order=1, og=_media("instrument"))
    _section(treatments, 0, "richtext", "Intro", eyebrow="Treatments and fees",
             title="Everything we do, with the numbers attached",
             subtitle="Bands, not headline prices. Your written estimate will sit inside the band "
                      "for your case.",
             body="A band exists because two people needing the same treatment rarely need the same "
                  "amount of work. What the band does not do is move once you have the estimate in "
                  "your hand.\n\nWhere EMI is available it is marked on the card. Everything above "
                  "fifteen thousand rupees can be spread over six to twenty-four months.",
             data={"width": "narrow", "tone": "light"})
    _section(treatments, 1, "services", "All treatments", anchor="all",
             title="", subtitle="",
             data={"mode": "all", "limit": 40, "show_price": 1, "cta_label": "", "cta_url": ""})
    _section(treatments, 2, "emi", "EMI", anchor="emi", eyebrow="Paying for it",
             title="Spread anything above fifteen thousand",
             data={"default_amount": 45000, "max_amount": 400000, "tone": "deep",
                   "points": _lines(
                       {"title": "Six to twelve months", "text": "No interest and no fee at all"},
                       {"title": "Eighteen and twenty-four", "text": "Interest shown before you apply"})})
    _section(treatments, 3, "faq", "Fee questions", eyebrow="Fees",
             title="Questions about money",
             data={"category": "Money", "limit": 6, "tone": "light"})
    _section(treatments, 4, "enquiry", "Enquiry", anchor="enquiry",
             title="Ask what your case would cost",
             subtitle="Tell us roughly what you need and reception will book you a consultation.",
             data={"show_service": 1, "show_branch": 1, "show_slot": 1, "tone": "canvas"})

    # ── EMI page ────────────────────────────────────────────────────────────
    emi_page = _page("emi-and-payment", "EMI and payment",
                     "No-cost dental EMI in Pune | Anvaya Dental Care",
                     "No-cost EMI from six to twelve months, longer plans with the interest stated "
                     "up front, decided in-house rather than by a lender.", order=2,
                     og=_media("desk"))
    _section(emi_page, 0, "richtext", "Intro", eyebrow="EMI and payment",
             title="Treatment now, paid across months, decided here",
             subtitle="We run our own instalment book. There is no third-party lender to reject "
                      "you and no salesperson on commission.",
             body="Anything above fifteen thousand rupees can be spread. The six, nine and twelve "
                  "month plans carry no interest and no processing fee, so you pay the treatment "
                  "price and nothing more.\n\nLonger plans do carry interest, and the calculator "
                  "below shows the exact rupee cost before you apply. We would rather you saw that "
                  "number than discovered it.",
             data={"width": "narrow", "tone": "light"})
    _section(emi_page, 1, "emi", "Calculator", anchor="calculator",
             title="Your monthly figure",
             subtitle="Set the treatment amount and compare every plan you qualify for.",
             data={"default_amount": 90000, "max_amount": 500000, "tone": "deep",
                   "points": _lines(
                       {"title": "What we need", "text": "PAN, one address proof and the plan"},
                       {"title": "How long it takes", "text": "Usually decided the same day"},
                       {"title": "What it costs to apply", "text": "Nothing, and no obligation"})})
    _section(emi_page, 2, "process", "How it works", eyebrow="The process",
             title="From apply to first instalment",
             data={"tone": "light", "items": _lines(
                 {"title": "Apply", "text": "Two minutes on the form below, or at reception."},
                 {"title": "Documents", "text": "PAN and address proof, photographed on your phone."},
                 {"title": "Decision", "text": "In-house, usually the same working day."},
                 {"title": "Schedule", "text": "You get the dated instalment list before treatment starts."},
             )})
    _section(emi_page, 3, "faq", "EMI questions", eyebrow="EMI",
             title="What patients ask about EMI",
             data={"category": "Money", "limit": 6, "tone": "canvas"})
    _section(emi_page, 4, "cta", "Band", title="Ready to spread the cost?",
             subtitle="Apply from the calculator above, or ring reception and do it over the phone.",
             data={"tone": "ink", "primary_label": "Call 020 4120 8800",
                   "primary_url": "tel:+912041208800",
                   "secondary_label": "Ask a question", "secondary_url": "/contact"})

    # ── about page ──────────────────────────────────────────────────────────
    about = _page("about", "The practice and the people",
                  "About Anvaya Dental Care, Pune | The practice and the people",
                  "Fifteen years, two clinics and nine clinicians in west Pune, with the same "
                  "founding dentist still on the floor.", order=3, og=_media("scans"))
    _section(about, 0, "richtext", "Intro", eyebrow="About Anvaya",
             title="Two rooms on Law College Road, fifteen years ago",
             subtitle="What has grown is the number of chairs. What has not changed is who is "
                      "sitting on the other side of them.",
             body="Dr Aditi Deshmukh opened Anvaya in 2011 after eight years in a hospital "
                  "prosthodontics unit, on the simple premise that most dental anxiety is really "
                  "anxiety about not being told things.\n\nSo we tell people things. The scan goes "
                  "on the screen. The estimate is itemised. The clinician who plans the case is the "
                  "one who does it, and their registration number is on their profile.",
             data={"width": "narrow", "tone": "light"})
    _section(about, 1, "doctors", "Clinicians", anchor="team", eyebrow="The team",
             title="Who you will meet",
             subtitle="Nine clinicians across two clinics. These four lead the lists.",
             data={"limit": 8, "tone": "canvas"})
    _section(about, 2, "about", "Sterilisation", eyebrow="Behind the door",
             title="The sterilisation room, and why we will show it to you",
             subtitle="Every instrument that touches you has a logged autoclave cycle behind it.",
             body="Instruments are scrubbed, ultrasonically cleaned, pouched, then autoclaved at "
                  "134 degrees. Each cycle is logged with the date, the load and the operator, and "
                  "we spore-test weekly.\n\nAsk at reception and you can read the log. Nobody ever "
                  "does, which is exactly why it stays honest.",
             data={"media_id": _media("instrument"), "flip": 1, "tone": "light",
                   "points": _lines(
                       {"title": "One tray per patient", "text": "Opened in front of you"},
                       {"title": "Logged cycles", "text": "Date, load and operator, kept on file"},
                       {"title": "Weekly spore test", "text": "Independent verification, filed"})})
    _section(about, 3, "gallery", "Clinics", eyebrow="Both clinics",
             title="Law College Road and Baner",
             data={"gallery_id": gallery_id, "layout": "grid", "tone": "canvas"})
    _section(about, 4, "cta", "Band", title="Come and see for yourself",
             subtitle="A consultation is fifty minutes and you leave with the plan in writing.",
             data={"tone": "ink", "primary_label": "Book an appointment", "primary_url": "/contact",
                   "secondary_label": "See treatments", "secondary_url": "/treatments"})

    # ── contact page ────────────────────────────────────────────────────────
    contact = _page("contact", "Contact and directions",
                    "Contact Anvaya Dental Care | Law College Road and Baner, Pune",
                    "Phone, WhatsApp, opening hours and directions for both Anvaya clinics in Pune.",
                    order=4, og=_media("interior"))
    _section(contact, 0, "richtext", "Intro", eyebrow="Contact",
             title="Ring, message or ask below",
             subtitle="Reception answers the phone during opening hours. Out of hours the emergency "
                      "number reaches a clinician.",
             data={"width": "narrow", "tone": "light"})
    _section(contact, 1, "branches", "Clinics", anchor="locations",
             title="Both clinics", subtitle="",
             data={"show_map": 1, "tone": "light"})
    _section(contact, 2, "enquiry", "Enquiry", anchor="enquiry",
             title="Send us a message",
             subtitle="Anything you would rather write down than say on the phone.",
             data={"show_service": 1, "show_branch": 1, "show_slot": 1, "tone": "canvas",
                   "side_points": _lines(
                       {"title": "Reception", "text": "020 4120 8800, 9.30am to 8pm Monday to Saturday"},
                       {"title": "Emergencies", "text": "+91 90000 12345, any hour, reaches a clinician"},
                       {"title": "Email", "text": "hello@anvayadental.in, answered within a working day"})})
    _section(contact, 3, "faq", "FAQ", eyebrow="Before you ring",
             title="Quick answers", data={"category": "General", "limit": 6, "tone": "light"})

    # ── funnel samples ──────────────────────────────────────────────────────
    for (name, phone, email, service, branch, slot, message, status, priority, days) in SAMPLE_ENQUIRIES:
        created = (date.today() - timedelta(days=days)).isoformat() + " 10:24:00"
        enq_id = db.insert("enquiries", {
            "ref": ref_code("ENQ"), "name": name, "phone": phone, "email": email,
            "service_id": service_ids.get(service), "branch_id": branch_ids.get(branch),
            "preferred_date": (date.today() + timedelta(days=max(1, 3 - days // 4))).isoformat(),
            "preferred_time": slot, "message": message, "status": status, "priority": priority,
            "source_page": "/", "utm": dump_json({}), "ip": "203.0.113.7",
            "user_agent": "seed", "created_at": created, "updated_at": created,
        })
        db.insert("enquiry_events", {"enquiry_id": enq_id, "type": "created",
                                     "note": "Submitted from the website form.",
                                     "created_at": created})
        if status != "new":
            db.insert("enquiry_events", {
                "enquiry_id": enq_id, "type": "status",
                "note": f"Status moved to {status}.",
                "created_at": (date.today() - timedelta(days=max(0, days - 1))).isoformat() + " 12:05:00",
            })

    _seed_emi_applications(service_ids)

    print("[seed] Anvaya Dental Care loaded: 5 pages, "
          f"{len(SERVICES)} treatments, {len(DOCTORS)} clinicians, {len(BRANCHES)} clinics, "
          f"{len(FAQS)} FAQs, {len(EMI_PLANS)} EMI plans, {len(SAMPLE_ENQUIRIES)} enquiries.")


def _seed_emi_applications(service_ids: dict) -> None:
    from core import emi as emi_core

    plans = db.query("SELECT * FROM emi_plans ORDER BY sort_order")
    if not plans:
        return
    plan_by_tenure = {p["tenure_months"]: p for p in plans}

    cases = [
        ("Deepak Gaikwad", "+91 88880 12234", "deepak.g@rediffmail.com",
         "Full mouth rehabilitation", 268000, 18, "active", 120),
        ("Ritika Sharma", "+91 90040 22119", "ritika.sharma@outlook.com",
         "Invisible aligners", 165000, 12, "approved", 6),
        ("Ketan Mhatre", "+91 98220 41188", "ketan.mhatre@gmail.com",
         "Dental implants", 52000, 9, "submitted", 1),
    ]

    for (name, phone, email, treatment, amount, tenure, status, days_ago) in cases:
        plan = plan_by_tenure.get(tenure) or plans[0]
        q = emi_core.quote_for_plan(amount, plan)
        start = date.today() - timedelta(days=days_ago)
        created = start.isoformat() + " 11:15:00"
        app_id = db.insert("emi_applications", {
            "ref": emi_core.new_application_ref(), "applicant_name": name, "phone": phone,
            "email": email, "service_id": service_ids.get(treatment),
            "treatment_label": treatment, "treatment_amount": amount, "plan_id": plan["id"],
            "plan_label": plan["name"], "tenure_months": tenure,
            "interest_rate": plan["interest_rate"], "processing_fee": q["processing_fee"],
            "downpayment": q["downpayment"], "financed": q["financed"],
            "monthly_emi": q["monthly_emi"], "total_payable": q["total_payable"],
            "status": status, "start_date": start.isoformat(),
            "notes": "Seeded example so the ledger is not empty on a fresh install.",
            "created_at": created, "updated_at": created,
        })

        if status in ("approved", "active"):
            emi_core.build_schedule(app_id)

        if status == "active":
            # mark the instalments whose due date has passed as paid, with receipts
            due = db.query(
                "SELECT * FROM emi_installments WHERE application_id = ? AND due_date <= date('now') "
                "ORDER BY seq", (app_id,))
            for inst in due:
                receipt = emi_core.next_receipt_no(str(settings.get("emi.receipt_prefix", "ANV")))
                pay_id = db.insert("payments", {
                    "receipt_no": receipt, "application_id": app_id, "installment_id": inst["id"],
                    "payer_name": name, "amount": inst["amount"], "method": "upi",
                    "provider": "", "provider_ref": f"UPI{inst['seq']:04d}{app_id}",
                    "status": "paid", "paid_at": inst["due_date"] + " 09:40:00",
                    "notes": f"Instalment {inst['seq']} of {tenure}",
                })
                db.update("emi_installments", inst["id"],
                          {"status": "paid", "paid_at": inst["due_date"] + " 09:40:00",
                           "payment_id": pay_id})
            # leave the most recent one unpaid so the overdue view has something in it
            last_paid = db.one(
                "SELECT * FROM emi_installments WHERE application_id = ? AND status = 'paid' "
                "ORDER BY seq DESC LIMIT 1", (app_id,))
            if last_paid:
                db.execute("DELETE FROM payments WHERE installment_id = ?", (last_paid["id"],))
                db.update("emi_installments", last_paid["id"],
                          {"status": "due", "paid_at": None, "payment_id": None})
