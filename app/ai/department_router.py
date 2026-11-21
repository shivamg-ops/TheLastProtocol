
import json
from pathlib import Path


# Locate department directory
DATA_FILE = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "departments.json"
)


def load_departments():

    with open(DATA_FILE, "r", encoding="utf-8") as file:
        data = json.load(file)

    return data["departments"]


def route_complaint(category):

    departments = load_departments()

    for department in departments:

        if category in department["categories"]:

            return {
                "department_id": department["id"],
                "department_name": department["name"],
                "routing_status": "matched"
            }

    return {
        "department_id": None,
        "department_name": None,
        "routing_status": "manual_review"
    }
