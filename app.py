import os
import json
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from scheduler import TimetableScheduler

app = Flask(__name__, static_folder='static', static_url_path='')
CORS(app)

DATA_FILE = os.path.join(os.path.dirname(__file__), 'timetable_data.json')

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print("Error loading data file:", e)
        return {}

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

@app.route('/api/generate', methods=['POST'])
def generate():
    data = load_data()
    req_body = request.get_json(silent=True)
    if req_body and "courses" in req_body:
        data.update(req_body)
        save_data(data)

    config = data.get("config", {})
    teachers = data.get("faculty", [])
    rooms = data.get("rooms", [])
    batches = data.get("batches", [])
    sub_batches = data.get("sub_batches", [])
    courses = data.get("courses", [])

    scheduler = TimetableScheduler(config, teachers, rooms, batches, courses, sub_batches=sub_batches)
    result = scheduler.generate(max_attempts=150)

    if result["success"]:
        # Prepend the fixed Basics of Civil Engineering slots
        combined = list(data.get("fixed_ce234p_schedule", [])) + result["schedule"]
        data["timetable"] = combined
        save_data(data)
        result["schedule"] = combined

    return jsonify(result)

@app.route('/api/timetable/update-slot', methods=['POST'])
def update_slot():
    data = load_data()
    body = request.get_json(force=True)
    entry_id = body.get("entry_id")
    target_day = body.get("target_day")
    target_period = body.get("target_period")
    target_room_id = body.get("target_room_id")

    tt = data.get("timetable", [])
    entry = next((e for e in tt if e.get("id") == entry_id), None)
    if not entry:
        return jsonify({"success": False, "message": "Entry not found"}), 404

    # Validation checks
    conflicts = []
    for other in tt:
        if other.get("id") == entry_id:
            continue
        if other.get("day") == target_day and other.get("period") == target_period:
            if other.get("teacher_id") and other.get("teacher_id") == entry.get("teacher_id"):
                conflicts.append(f"Faculty conflict: {entry.get('teacher_name')} already teaching.")
            if other.get("batch_id") == entry.get("batch_id"):
                conflicts.append(f"Batch conflict: {entry.get('batch_name')} already has a class.")
            if target_room_id and other.get("room_id") == target_room_id:
                conflicts.append(f"Room collision: {other.get('room_name')} is occupied.")

    entry["day"] = target_day
    days_list = data["config"].get("days", [])
    entry["day_name"] = days_list[target_day] if target_day < len(days_list) else f"Day {target_day+1}"
    entry["period"] = target_period
    
    # Update period name and time
    periods_list = data["config"].get("periods", [])
    if target_period < len(periods_list):
        entry["period_name"] = periods_list[target_period].get("name")
        entry["period_time"] = periods_list[target_period].get("time")

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
    if not tt:
        tt = data.get("fixed_ce234p_schedule", [])
    
    rows = ["Day,Period,Timing,Batch,Sub-Batch,Course Code,Course Name,Faculty,Room,Is Lab"]
    for e in sorted(tt, key=lambda x: (x.get('batch_name', ''), x.get('day', 0), x.get('period', 0))):
        rows.append(f'"{e.get("day_name","")}","{e.get("period",0)+1}","{e.get("period_time","")}","{e.get("batch_name","")}","{e.get("sub_batch_name","")}","{e.get("course_code","")}","{e.get("course_name","")}","{e.get("teacher_name","TBD")}","{e.get("room_name","")}","{e.get("is_lab",False)}"')
    
    csv_text = "\n".join(rows)
    return csv_text, 200, {
        'Content-Type': 'text/csv; charset=utf-8',
        'Content-Disposition': 'attachment; filename="civil_timetable_2026_27.csv"'
    }

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    print(f"🚀 Timetable Portal running on http://127.0.0.1:{port}")
    app.run(host='0.0.0.0', port=port, debug=True)
