import uuid
from django.core.management.base import BaseCommand
from django.utils import timezone
from api.models import (
    Department, ComplaintCategory, User, UserRole,
    Complaint, ComplaintStatus, PriorityLevel, ComplaintTimeline,
    ComplaintEvidence, CitizenFeedback, Subscription
)

class Command(BaseCommand):
    help = 'Seeds realistic, clearly labeled demo complaints across all 6 civic categories and 4 languages'

    def handle(self, *args, **kwargs):
        self.stdout.write("Starting Demo Data Seeding for Hackathon...")

        # 1. Ensure Standard Demo Users Exist
        admin_user, _ = User.objects.get_or_create(
            username="admin",
            defaults={"email": "admin@jansahayak.gov.in", "role": UserRole.ADMIN, "first_name": "Municipal", "last_name": "Commissioner"}
        )
        if not admin_user.has_usable_password():
            admin_user.set_password("adminpassword123")
            admin_user.is_staff = True
            admin_user.is_superuser = True
            admin_user.save()

        staff_user, _ = User.objects.get_or_create(
            username="staff1",
            defaults={"email": "staff1@jansahayak.gov.in", "role": UserRole.STAFF, "first_name": "Ramesh", "last_name": "Shinde", "organization_name": "Zone 4 Field Action Unit"}
        )
        if not staff_user.has_usable_password():
            staff_user.set_password("staffpassword123")
            staff_user.save()

        citizen_user, _ = User.objects.get_or_create(
            username="citizen1",
            defaults={"email": "citizen1@example.com", "role": UserRole.CITIZEN, "first_name": "Aarav", "last_name": "Sharma", "phone_number": "+91-9876543210"}
        )
        if not citizen_user.has_usable_password():
            citizen_user.set_password("citizenpassword123")
            citizen_user.save()

        Subscription.objects.get_or_create(user=citizen_user, defaults={"tier": "free"})

        # 2. Map Categories
        categories = {c.slug: c for c in ComplaintCategory.objects.all()}
        if not categories:
            self.stdout.write(self.style.ERROR("No categories found. Run 'python manage.py seed_data' first."))
            return

        # 3. Clean up existing DEMO complaints
        deleted_count, _ = Complaint.objects.filter(title__startswith="[DEMO]").delete()
        if deleted_count > 0:
            self.stdout.write(f"Purged {deleted_count} previous [DEMO] complaint records.")

        demo_cases = [
            {
                "title": "[DEMO] Overflowing Garbage Dump Near Primary School",
                "category": categories.get("garbage-and-sanitation"),
                "detected_lang": "hi",
                "priority": PriorityLevel.HIGH,
                "status": ComplaintStatus.IN_PROGRESS,
                "address": "Opposite Bal Vikas School, Sector 4, Gandhinagar",
                "ward": "Ward 4",
                "duration": "4 days",
                "description": "स्कूल के पास पिछले 4 दिनों से कचरा नहीं उठाया गया है। बहुत बदबू आ रही है और आवारा मवेशी जमा हो रहे हैं। (Hindi Input Recorded via Voice)",
                "summary": "Municipal waste uncollected for 4 days near school premises causing health hazard.",
                "assigned": staff_user,
            },
            {
                "title": "[DEMO] Main Pipeline Burst & Water Wastage",
                "category": categories.get("water-supply"),
                "detected_lang": "mr",
                "priority": PriorityLevel.URGENT,
                "status": ComplaintStatus.ASSIGNED,
                "address": "Near Datta Mandir Chowk, Shivaji Nagar",
                "ward": "Ward 9",
                "duration": "12 hours",
                "description": "मुख्य जलवाहिनी फुटल्याने रस्त्यावर लाखो लिटर पाणी वाया जात आहे आणि घरात पाण्याचा दाब कमी झाला आहे. (Marathi Input Recorded via Voice)",
                "summary": "High-pressure potable water pipeline rupture at main road intersection.",
                "assigned": staff_user,
            },
            {
                "title": "[DEMO] Dangerous Monsoon Crater on Ring Road",
                "category": categories.get("roads-and-potholes"),
                "detected_lang": "en",
                "priority": PriorityLevel.URGENT,
                "status": ComplaintStatus.RESOLVED,
                "address": "Ring Road Phase 2, Near Pillar 142",
                "ward": "Ward 14",
                "duration": "1 week",
                "description": "Deep asphalt crater measuring 2 feet wide on the curve of Ring Road. Two bikers already skidded yesterday night.",
                "summary": "Hazardous road crater on major traffic arterial causing vehicular accidents.",
                "assigned": staff_user,
                "notes": "Emergency cold-mix asphalt applied; patch leveled and roller compacted on Nov 21.",
                "feedback": {
                    "rating": 5,
                    "text": "Fixed within 24 hours of filing! Very impressed by municipal response.",
                    "satisfaction": True
                }
            },
            {
                "title": "[DEMO] Clogged Stormwater Drain & Sewage Backflow",
                "category": categories.get("drainage-and-sewage"),
                "detected_lang": "hinglish",
                "priority": PriorityLevel.HIGH,
                "status": ComplaintStatus.SUBMITTED,
                "address": "Gali No. 7, Behind City Mall, Vikas Nagar",
                "ward": "Ward 12",
                "duration": "2 days",
                "description": "Gutter ka paani block ho gaya hai aur black water sadak par nikal raha hai. Please jetting machine dispatch karein.",
                "summary": "Sewage backflow spilling onto residential street due to solid waste blockage.",
                "assigned": None,
            },
            {
                "title": "[DEMO] Streetlight Pole Dark for 500m Stretch",
                "category": categories.get("streetlights"),
                "detected_lang": "en",
                "priority": PriorityLevel.MEDIUM,
                "status": ComplaintStatus.IN_PROGRESS,
                "address": "4th Cross Road, Lakeview Colony",
                "ward": "Ward 3",
                "duration": "5 days",
                "description": "Entire row of 6 sodium vapour streetlights is dark creating security concerns for late-night commuters.",
                "summary": "Underground cable short circuit causing darkness along residential avenue.",
                "assigned": staff_user,
            },
            {
                "title": "[DEMO] Commercial Delivery Encroachment on Pedestrian Footpath",
                "category": categories.get("traffic-and-road-obstruction"),
                "detected_lang": "hi",
                "priority": PriorityLevel.MEDIUM,
                "status": ComplaintStatus.SUBMITTED,
                "address": "Station Road Market, Near Metro Exit Gate 2",
                "ward": "Ward 1",
                "duration": "Ongoing",
                "description": "दुकानदारों ने फुटपाथ पर सामान रखकर रास्ता बंद कर दिया है, पैदल चलने वालों को मुख्य सड़क पर चलना पड़ रहा है।",
                "summary": "Sidewalk commercial encroachment forcing pedestrians into high-speed vehicular traffic.",
                "assigned": None,
            }
        ]

        now = timezone.now()
        for idx, item in enumerate(demo_cases):
            cat = item["category"]
            dept = cat.department if cat else None
            tracking_id = f"JSH-DEMO0{idx + 1}"

            comp = Complaint.objects.create(
                tracking_id=tracking_id,
                citizen=citizen_user,
                title=item["title"],
                description=item["description"],
                category=cat,
                department=dept,
                status=item["status"],
                priority=item["priority"],
                address=item["address"],
                ward_or_zone=item["ward"],
                duration_of_issue=item["duration"],
                detected_language=item["detected_lang"],
                original_input_mode="voice",
                ai_generated_summary=item["summary"],
                assigned_staff=item["assigned"],
                assigned_at=now if item["assigned"] else None,
                resolution_notes=item.get("notes"),
                resolution_date=now if item["status"] == ComplaintStatus.RESOLVED else None
            )

            # Timeline
            ComplaintTimeline.objects.create(
                complaint=comp,
                performed_by=citizen_user,
                action="Complaint Registered (Voice Intake)",
                details="Logged via JanSahayak AI Multilingual Assistant",
                to_status=ComplaintStatus.SUBMITTED
            )

            if item["assigned"]:
                ComplaintTimeline.objects.create(
                    complaint=comp,
                    performed_by=admin_user,
                    action=f"Dispatched to {item['assigned'].username}",
                    details="Staff dispatched based on Ward and Department SLA."
                )

            if item["status"] == ComplaintStatus.RESOLVED:
                ComplaintTimeline.objects.create(
                    complaint=comp,
                    performed_by=staff_user,
                    action="Resolved in Field",
                    details=item.get("notes", "Resolution work executed."),
                    from_status=ComplaintStatus.IN_PROGRESS,
                    to_status=ComplaintStatus.RESOLVED
                )

                if "feedback" in item:
                    fb = item["feedback"]
                    CitizenFeedback.objects.create(
                        complaint=comp,
                        rating=fb["rating"],
                        feedback_text=fb["text"],
                        resolution_satisfaction=fb["satisfaction"]
                    )
                    comp.status = ComplaintStatus.VERIFIED
                    comp.save(update_fields=['status'])

                    ComplaintTimeline.objects.create(
                        complaint=comp,
                        performed_by=citizen_user,
                        action="Citizen Rating & Verification",
                        details=f"Rated {fb['rating']}/5: {fb['text']}",
                        to_status=ComplaintStatus.VERIFIED
                    )

            self.stdout.write(f"Seeded: {comp.tracking_id} [{comp.category.name if comp.category else 'General'}] -> {comp.status}")

        self.stdout.write(self.style.SUCCESS("\nDemo Seed Completed! 6 Multi-lingual, Multi-category Complaints Ready for Presentation."))

