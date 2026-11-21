from django.core.management.base import BaseCommand
from api.models import Department, ComplaintCategory, User, UserRole

class Command(BaseCommand):
    help = 'Seeds initial departments and standard civic categories'

    def handle(self, *args, **kwargs):
        departments = [
            {"name": "Solid Waste Management", "code": "SWM", "icon": "Trash2", "sla_hours": 24, "description": "Garbage disposal, street sweeping, cleanliness"},
            {"name": "Water Supply & Sewerage", "code": "WSS", "icon": "Droplet", "sla_hours": 36, "description": "Drinking water pipelines, contamination, shortages"},
            {"name": "Roads & Traffic Infrastructure", "code": "RTI", "icon": "Construction", "sla_hours": 72, "description": "Potholes, asphalt resurfacing, zebra crossings"},
            {"name": "Electrical & Street Lighting", "code": "ESL", "icon": "Lightbulb", "sla_hours": 24, "description": "Streetlights, exposed electrical boxes, dark spots"},
            {"name": "Stormwater & Drainage", "code": "SWD", "icon": "Waves", "sla_hours": 48, "description": "Gutter cleaning, clogged drains, monsoon overflow"},
            {"name": "Traffic & Encroachment Control", "code": "TEC", "icon": "Car", "sla_hours": 24, "description": "Illegal parking, sidewalk vendors, blocked streets"}
        ]

        created_depts = {}
        for d in departments:
            dept, created = Department.objects.get_or_create(
                code=d["code"],
                defaults={
                    "name": d["name"],
                    "icon": d["icon"],
                    "sla_hours": d["sla_hours"],
                    "description": d["description"]
                }
            )
            created_depts[d["code"]] = dept
            self.stdout.write(f"Department: {dept.name}")

        categories = [
            {"name": "Garbage and Sanitation", "slug": "garbage-and-sanitation", "dept_code": "SWM", "priority": "medium", "desc": "Overflowing bins, uncollected waste, public litter"},
            {"name": "Water Supply", "slug": "water-supply", "dept_code": "WSS", "priority": "high", "desc": "Pipe burst, low pressure, dirty water, tap leakages"},
            {"name": "Roads and Potholes", "slug": "roads-and-potholes", "dept_code": "RTI", "priority": "urgent", "desc": "Potholes, road damage, uneven surfacing"},
            {"name": "Streetlights", "slug": "streetlights", "dept_code": "ESL", "priority": "medium", "desc": "Non-functional lights, flickering bulb, broken pole"},
            {"name": "Drainage and Sewage", "slug": "drainage-and-sewage", "dept_code": "SWD", "priority": "high", "desc": "Blocked drainage, sewer backflow, open manhole"},
            {"name": "Traffic and Road Obstruction", "slug": "traffic-and-road-obstruction", "dept_code": "TEC", "priority": "medium", "desc": "Illegal vehicle parking, footpath encroachments"}
        ]

        for c in categories:
            cat, created = ComplaintCategory.objects.get_or_create(
                slug=c["slug"],
                defaults={
                    "name": c["name"],
                    "department": created_depts.get(c["dept_code"]),
                    "priority_default": c["priority"],
                    "description": c["desc"]
                }
            )
            self.stdout.write(f"Category: {cat.name}")

        # Note: Users should be created via createsuperuser or API registration
        self.stdout.write(self.style.SUCCESS("Database seeding completed successfully!"))

