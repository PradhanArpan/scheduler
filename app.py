import os
import json
from flask import Flask, request, jsonify, send_from_directory, render_template_string
from flask_cors import CORS
from scheduler import TimetableScheduler

app = Flask(__name__, static_folder='static', static_url_path='')
CORS(app)

DATA_FILE = os.path.join(os.path.dirname(__file__), 'timetable_data.json')

DEFAULT_SAMPLE_DATA = {
    "config": {
        "title": "Engineering Department Master Timetable",
        "academic_year": "2026-2027",
        "semester": "Odd Semester",
        "days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
        "periods_per_day": 6,
        "recess_after_period": 3,
        "period_times": [
            "09:00 - 10:00",
            "10:00 - 11:00",
            "11:00 - 12:00",
            "01:00 - 02:00",
            "02:00 - 03:00",
            "03:00 - 04:00"
        ]
    },
    "departments": [
        {"id": "dept_1", "name": "Civil Engineering"}
    ],
    "batches": [
        {"id": "batch_1", "name": "3rd Sem (Section A)", "department_id": "dept_1"},
        {"id": "batch_2", "name": "5th Sem (Section A)", "department_id": "dept_1"}
    ],
    "teachers": [
        {
            "id": "t_1",
            "name": "Dr. Arpan Pradhan",
            "code": "AP",
            "department": "Civil Engineering",
            "email": "arpan@dept.edu",
            "unavailable_slots": [{"day": 0, "period": 0}] # Not available Mon Period 1
        },
        {
            "id": "t_2",
            "name": "Prof. S. Sharma",
            "code": "SS",
            "department": "Civil Engineering",
            "email": "sharma@dept.edu",
            "unavailable_slots": []
        },
        {
            "id": "t_3",
            "name": "Dr. R. Verma",
            "code": "RV",
            "department": "Civil Engineering",
            "email": "verma@dept.edu",
            "unavailable_slots": [{"day": 4, "period": 5}] # Friday late afternoon
        },
        {
            "id": "t_4",
            "name": "Prof. K. Roy",
            "code": "KR",
            "department": "Applied Sciences",
            "email": "roy@dept.edu",
            "unavailable_slots": []
        }
    ],
    "rooms": [
        {"id": "r_101", "name": "Room 101 (LH)", "type": "Lecture", "capacity": 60},
        {"id": "r_102", "name": "Room 102 (LH)", "type": "Lecture", "capacity": 60},
        {"id": "r_lab1", "name": "Structures Lab", "type": "Lab", "capacity": 30},
        {"id": "r_lab2", "name": "CAD / Survey Lab", "type": "Lab", "capacity": 30}
    ],
    "courses": [
        # Batch 1 Courses (3rd Sem)
        {
            "id": "c_1",
            "name": "Structural Analysis I",
            "code": "CE301",
            "batch_id": "batch_1",
            "teacher_id": "t_1",
            "weekly_periods": 4,
            "block_size": 1,
            "room_type": "Lecture",
            "preferred_room_id": "r_101",
            "is_lab": False
        },
        {
            "id": "c_2",
            "name": "Fluid Mechanics",
            "code": "CE302",
            "batch_id": "batch_1",
            "teacher_id": "t_2",
            "weekly_periods": 4,
            "block_size": 1,
            "room_type": "Lecture",
            "preferred_room_id": "r_101",
            "is_lab": False
        },
        {
            "id": "c_3",
            "name": "Engineering Mathematics III",
            "code": "MA301",
            "batch_id": "batch_1",
            "teacher_id": "t_4",
            "weekly_periods": 4,
            "block_size": 1,
            "room_type": "Lecture",
            "preferred_room_id": "r_101",
            "is_lab": False
        },
        {
            "id": "c_4",
            "name": "Surveying Lab",
            "code": "CE303L",
            "batch_id": "batch_1",
            "teacher_id": "t_3",
            "weekly_periods": 2,
            "block_size": 2, # 2 consecutive periods
            "room_type": "Lab",
            "preferred_room_id": "r_lab2",
            "is_lab": True
        },
        # Batch 2 Courses (5th Sem)
        {
            "id": "c_5",
            "name": "Design of RC Structures",
            "code": "CE501",
            "batch_id": "batch_2",
            "teacher_id": "t_1",
            "weekly_periods": 4,
            "block_size": 1,
            "room_type": "Lecture",
            "preferred_room_id": "r_102",
            "is_lab": False
        },
        {
            "id": "c_6",
            "name": "Geotechnical Engineering",
            "code": "CE502",
            "batch_id": "batch_2",
            "teacher_id": "t_2",
            "weekly_periods": 4,
            "block_size": 1,
            "room_type": "Lecture",
            "preferred_room_id": "r_102",
            "is_lab": False
        },
        {
            "id": "c_7",
            "name": "Transportation Engineering",
            "code": "CE503",
            "batch_id": "batch_2",
            "teacher_id": "t_3",
            "weekly_periods": 4,
            "block_size": 1,
            "room_type": "Lecture",
            "preferred_room_id": "r_102",
            "is_lab": False
        },
        {
            "id": "c_8",
            "name": "Structures & Concrete Lab",
            "code": "CE504L",
            "batch_id": "batch_2",
            "teacher_id": "t_1",
            "weekly_periods": 2,
            "block_size": 2, # 2 consecutive periods
            "room_type": "Lab",
            "preferred_room_id": "r_lab1",
            "is_lab": True
        }
    ],
    "timetable": []
}

def load_data():
    if not os.path.exists(DATA_FILE):
        save_data(DEFAULT_SAMPLE_DATA)
        return DEFAULT_SAMPLE_DATA
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return DEFAULT_SAMPLE_DATA

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/api/state', methods=['GET'])
def get_state():
    data = load_data()
    return jsonify(data)

@app.route('/api/state', methods=['POST'])
def update_state():
    new_data = request.get_json(force=True)
    save_data(new_data)
    return jsonify({"success": True, "message": "State saved successfully."})

@app.route('/api/reset-sample', methods=['POST'])
def reset_sample():
    save_data(DEFAULT_SAMPLE_DATA)
    return jsonify({"success": True, "data": DEFAULT_SAMPLE_DATA})

@app.route('/api/generate', methods=['POST'])
def generate():
    data = load_data()
    req_body = request.get_json(silent=True)
    if req_body and "courses" in req_body:
        # Override with posted data if provided
        data.update(req_body)
        save_data(data)

    config = data.get("config", {})
    teachers = data.get("teachers", [])
    rooms = data.get("rooms", [])
    batches = data.get("batches", [])
    courses = data.get("courses", [])

    scheduler = TimetableScheduler(config, teachers, rooms, batches, courses)
    result = scheduler.generate(max_attempts=100)

    if result["success"]:
        data["timetable"] = result["schedule"]
        save_data(data)

    return jsonify(result)

@app.route('/api/timetable/update-slot', methods=['POST'])
def update_slot():
    """Manually move or swap an entry with live conflict validation"""
    data = load_data()
    body = request.get_json(force=True)
    entry_id = body.get("entry_id")
    target_day = body.get("target_day")
    target_period = body.get("target_period")
    target_room_id = body.get("target_room_id")

    tt = data.get("timetable", [])
    entry = next((e for e in tt if e["id"] == entry_id), None)
    if not entry:
        return jsonify({"success": False, "message": "Entry not found"}), 404

    # Check conflicts at target
    conflicts = []
    for other in tt:
        if other["id"] == entry_id:
            continue
        if other["day"] == target_day and other["period"] == target_period:
            if other["teacher_id"] == entry["teacher_id"]:
                conflicts.append(f"Teacher {entry['teacher_name']} is already teaching {other['course_name']} in this slot.")
            if other["batch_id"] == entry["batch_id"]:
                conflicts.append(f"Batch {entry['batch_name']} already has {other['course_name']} in this slot.")
            if target_room_id and other["room_id"] == target_room_id:
                conflicts.append(f"Room {other['room_name']} is occupied by {other['batch_name']}.")

    # Apply move
    entry["day"] = target_day
    entry["day_name"] = data["config"]["days"][target_day]
    entry["period"] = target_period
    period_times = data["config"].get("period_times", [])
    entry["period_time"] = period_times[target_period] if target_period < len(period_times) else f"Period {target_period+1}"
    if target_room_id:
        room_obj = next((r for r in data.get("rooms", []) if r["id"] == target_room_id), None)
        if room_obj:
            entry["room_id"] = room_obj["id"]
            entry["room_name"] = room_obj["name"]

    save_data(data)
    return jsonify({
        "success": True,
        "conflicts": conflicts,
        "timetable": tt
    })

@app.route('/api/export/csv', methods=['GET'])
def export_csv():
    data = load_data()
    tt = data.get("timetable", [])
    days = data["config"]["days"]
    
    rows = ["Day,Period,Timing,Batch,Course Code,Course Name,Teacher,Room,Is Lab"]
    for e in sorted(tt, key=lambda x: (x['batch_name'], x['day'], x['period'])):
        rows.append(f'"{e.get("day_name","")}","{e.get("period",0)+1}","{e.get("period_time","")}","{e.get("batch_name","")}","{e.get("course_code","")}","{e.get("course_name","")}","{e.get("teacher_name","")}","{e.get("room_name","")}","{e.get("is_lab",False)}"')
    
    csv_text = "\n".join(rows)
    return csv_text, 200, {
        'Content-Type': 'text/csv; charset=utf-8',
        'Content-Disposition': 'attachment; filename="master_timetable.csv"'
    }

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    print(f"🚀 Timetable Portal running on http://127.0.0.1:{port}")
    app.run(host='0.0.0.0', port=port, debug=True)
