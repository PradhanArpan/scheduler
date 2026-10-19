import os
import json
from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS
from scheduler import TimetableScheduler
import exporter

app = Flask(__name__, static_folder='static', static_url_path='')
CORS(app)

import shutil

IS_VERCEL = os.environ.get("VERCEL") == "1"

# Look for timetable_data.json across script dir, parent dir, or current working dir
_script_dir = os.path.dirname(os.path.abspath(__file__))
_parent_dir = os.path.abspath(os.path.join(_script_dir, '..'))
_cwd = os.getcwd()

_candidates = [
    os.path.join(_script_dir, 'timetable_data.json'),
    os.path.join(_parent_dir, 'timetable_data.json'),
    os.path.join(_cwd, 'timetable_data.json'),
    os.path.join(_cwd, 'api', 'timetable_data.json'),
]
BASE_DATA_FILE = next((p for p in _candidates if os.path.exists(p)), _candidates[0])

if IS_VERCEL:
    DATA_FILE = os.path.join('/tmp', 'timetable_data.json')
else:
    DATA_FILE = BASE_DATA_FILE

def load_data():
    target = DATA_FILE
    if IS_VERCEL and not os.path.exists(target):
        if os.path.exists(BASE_DATA_FILE):
            try:
                shutil.copyfile(BASE_DATA_FILE, target)
            except Exception as e:
                print("Could not copy base data to /tmp:", e)
                target = BASE_DATA_FILE
    if not os.path.exists(target):
        if os.path.exists(BASE_DATA_FILE):
            target = BASE_DATA_FILE
        else:
            return {}
    try:
        with open(target, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print("Error loading data file:", e)
        return {}

def save_data(data):
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print("Warning: unable to write to DATA_FILE:", e)

ALIAS_ROOM_MAP = {}

def sync_venue_names_and_ids(data):
    if not data:
        return
    rooms_list = data.get("rooms", [])
    rooms_by_id = {r["id"]: r for r in rooms_list}
    rooms_by_name = {r["name"]: r for r in rooms_list}
    if not rooms_by_id:
        return

    def resolve_entry_room(entry):
        rid = entry.get("room_id")
        if rid and rid in ALIAS_ROOM_MAP:
            rid = ALIAS_ROOM_MAP[rid]
            entry["room_id"] = rid

        # 1. Match by room_id
        if rid and rid in rooms_by_id:
            entry["room_name"] = rooms_by_id[rid]["name"]
        # 2. Match by existing room_name
        elif entry.get("room_name") and entry["room_name"] in rooms_by_name:
            matched = rooms_by_name[entry["room_name"]]
            entry["room_id"] = matched["id"]
            entry["room_name"] = matched["name"]

    # 1. Sync timetable entries
    for e in data.get("timetable", []):
        resolve_entry_room(e)

    # 2. Sync fixed schedules
    for e in data.get("fixed_ce234p_schedule", []):
        resolve_entry_room(e)
    for e in data.get("fixed_physics_schedule", []):
        resolve_entry_room(e)

    # 3. Sync batches default_room_id
    for b in data.get("batches", []):
        if b.get("default_room_id") in ALIAS_ROOM_MAP:
            b["default_room_id"] = ALIAS_ROOM_MAP[b["default_room_id"]]
        if b.get("default_room_id") in rooms_by_id:
            b["default_room_name"] = rooms_by_id[b["default_room_id"]]["name"]

    # 4. Sync unmapped_subjects preferred_room_id and fixed_slots
    for s in data.get("unmapped_subjects", []):
        if s.get("preferred_room_id") in ALIAS_ROOM_MAP:
            s["preferred_room_id"] = ALIAS_ROOM_MAP[s["preferred_room_id"]]
        for fs in s.get("fixed_slots", []):
            if fs.get("room_id") in ALIAS_ROOM_MAP:
                fs["room_id"] = ALIAS_ROOM_MAP[fs["room_id"]]
            if fs.get("room_id") in rooms_by_id:
                fs["room_name"] = rooms_by_id[fs["room_id"]]["name"]

def sync_fixed_schedule_teachers(data, sem_type=None):
    if not data:
        return
    if sem_type is None:
        sem_type = data.get("config", {}).get("semester", "Even Semester")
    
    sem_key = "Odd" if "Odd" in str(sem_type) else "Even"
    teachers_by_id = {t["id"]: t for t in data.get("faculty", [])}
    rooms_by_id = {r["id"]: r for r in data.get("rooms", [])}
    
    # First sync all venue names across all data models
    sync_venue_names_and_ids(data)
    
    # Map (batch_id, course_code) -> subject for active semester
    subject_lookup = {}
    for s in data.get("unmapped_subjects", []):
        s_sem = s.get("semester_type", "Even")
        if s_sem == sem_key or not s.get("semester_type"):
            subject_lookup[(s.get("batch_id"), s.get("code"))] = s
            
    # Update fixed_ce234p_schedule
    fixed_schedule = data.get("fixed_ce234p_schedule", [])
    for entry in fixed_schedule:
        b_id = entry.get("batch_id")
        code = entry.get("course_code")
        matched = subject_lookup.get((b_id, code))
        
        if not entry.get("id"):
            safe_code = str(code).replace(' ', '_').replace('-', '_')
            entry["id"] = f"fixed_{b_id}_{safe_code}_d{entry.get('day')}_p{entry.get('period')}"
            
        if matched:
            t_ids = matched.get("teacher_ids") or ([matched["teacher_id"]] if matched.get("teacher_id") else [])
            t_ids = [tid for tid in t_ids if tid]
            entry["teacher_ids"] = t_ids
            entry["teacher_id"] = t_ids[0] if t_ids else ""
            names = [teachers_by_id[tid]["name"] for tid in t_ids if tid in teachers_by_id]
            codes = [teachers_by_id[tid]["code"] for tid in t_ids if tid in teachers_by_id]
            entry["teacher_name"] = " & ".join(names) if names else "TBD"
            entry["teacher_code"] = "/".join(codes) if codes else ""
            entry["course_id"] = matched.get("id", "")
            
            # Ensure room is assigned if missing
            pref_r = matched.get("preferred_room_id")
            if pref_r and pref_r in rooms_by_id:
                entry["room_id"] = pref_r
                entry["room_name"] = rooms_by_id[pref_r]["name"]
            elif not entry.get("room_name"):
                default_lab = next((r for r in data.get("rooms", []) if r.get("type") == "Lab"), None)
                default_lh = next((r for r in data.get("rooms", []) if r.get("type") != "Lab"), None)
                if entry.get("is_lab") and default_lab:
                    entry["room_id"] = default_lab["id"]
                    entry["room_name"] = default_lab["name"]
                elif default_lh:
                    entry["room_id"] = default_lh["id"]
                    entry["room_name"] = default_lh["name"]
        else:
            if "teacher_ids" not in entry:
                entry["teacher_ids"] = []
                entry["teacher_id"] = ""
                entry["teacher_name"] = "TBD"
                entry["teacher_code"] = ""

    # Also update fixed_physics_schedule if present
    for entry in data.get("fixed_physics_schedule", []):
        b_id = entry.get("batch_id")
        code = entry.get("course_code")
        matched = subject_lookup.get((b_id, code))
        if matched:
            t_ids = matched.get("teacher_ids") or ([matched["teacher_id"]] if matched.get("teacher_id") else [])
            t_ids = [tid for tid in t_ids if tid]
            entry["teacher_ids"] = t_ids
            entry["teacher_id"] = t_ids[0] if t_ids else ""
            names = [teachers_by_id[tid]["name"] for tid in t_ids if tid in teachers_by_id]
            codes = [teachers_by_id[tid]["code"] for tid in t_ids if tid in teachers_by_id]
            entry["teacher_name"] = " & ".join(names) if names else "TBD"
            entry["teacher_code"] = "/".join(codes) if codes else ""
                
    # Update ALL timetable entries with latest assigned teachers from subject catalog
    tt = data.get("timetable", [])
    if tt:
        fixed_map = {(e.get("batch_id"), e.get("course_code"), e.get("day"), e.get("period")): e for e in fixed_schedule}
        for item in tt:
            b_id = item.get("batch_id")
            code = item.get("course_code")
            matched = subject_lookup.get((b_id, code))
            if not matched and code:
                matched = next((s for s in data.get("unmapped_subjects", []) if s.get("code") == code), None)
            if matched:
                t_ids = matched.get("teacher_ids") or ([matched["teacher_id"]] if matched.get("teacher_id") else [])
                t_ids = [tid for tid in t_ids if tid]
                item["teacher_ids"] = t_ids
                item["teacher_id"] = t_ids[0] if t_ids else ""
                names = [teachers_by_id[tid]["name"] for tid in t_ids if tid in teachers_by_id]
                codes = [teachers_by_id[tid]["code"] for tid in t_ids if tid in teachers_by_id]
                item["teacher_name"] = " & ".join(names) if names else "TBD"
                item["teacher_code"] = "/".join(codes) if codes else ""

            key = (item.get("batch_id"), item.get("course_code"), item.get("day"), item.get("period"))
            if key in fixed_map:
                f_item = fixed_map[key]
                if f_item.get("room_name"):
                    item["room_id"] = f_item.get("room_id")
                    item["room_name"] = f_item.get("room_name")

    # Final pass to ensure all timetable entries have updated room names
    sync_venue_names_and_ids(data)

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/api/state', methods=['GET'])
def get_state():
    data = load_data()
    sync_fixed_schedule_teachers(data)
    return jsonify(data)

@app.route('/api/state', methods=['POST'])
def update_state():
    new_data = request.get_json(force=True)
    import time
    if "_last_modified" not in new_data:
        new_data["_last_modified"] = int(time.time() * 1000)
    sync_fixed_schedule_teachers(new_data)
    save_data(new_data)
    return jsonify({"success": True, "message": "State saved successfully.", "_last_modified": new_data.get("_last_modified")})

@app.route('/api/precheck', methods=['POST'])
def precheck():
    data = load_data()
    req_body = request.get_json(silent=True) or {}
    sem_type = req_body.get("semester", data.get("config", {}).get("semester", "Even Semester"))
    sync_fixed_schedule_teachers(data, sem_type)
    
    config = data.get("config", {})
    teachers = data.get("faculty", [])
    rooms = data.get("rooms", [])
    batches = data.get("batches", [])
    sub_batches = data.get("sub_batches", [])
    
    all_subjects = data.get("unmapped_subjects", [])
    if "Even" in sem_type:
        active_courses = [s for s in all_subjects if (s.get("semester_type") == "Even" or not s.get("semester_type"))]
    elif "Odd" in sem_type:
        active_courses = [s for s in all_subjects if s.get("semester_type") == "Odd"]
    else:
        active_courses = all_subjects

    scheduler = TimetableScheduler(config, teachers, rooms, batches, active_courses, sub_batches=sub_batches, fixed_schedule=data.get("fixed_ce234p_schedule", []))
    report = scheduler.pre_check_feasibility()
    return jsonify(report)

@app.route('/api/generate', methods=['POST'])
def generate():
    data = load_data()
    req_body = request.get_json(silent=True) or {}
    if "unmapped_subjects" in req_body:
        data["unmapped_subjects"] = req_body["unmapped_subjects"]

    config = data.get("config", {})
    teachers = data.get("faculty", [])
    rooms = data.get("rooms", [])
    batches = data.get("batches", [])
    sub_batches = data.get("sub_batches", [])
    
    sem_type = req_body.get("semester", config.get("semester", "Even Semester"))
    sync_fixed_schedule_teachers(data, sem_type)
    save_data(data)
    
    all_subjects = data.get("unmapped_subjects", [])
    if "Even" in sem_type:
        active_courses = [s for s in all_subjects if (s.get("semester_type") == "Even" or not s.get("semester_type"))]
    elif "Odd" in sem_type:
        active_courses = [s for s in all_subjects if s.get("semester_type") == "Odd"]
    else:
        active_courses = all_subjects

    scheduler = TimetableScheduler(config, teachers, rooms, batches, active_courses, sub_batches=sub_batches, fixed_schedule=data.get("fixed_ce234p_schedule", []))
    result = scheduler.generate(max_attempts=30)

    if result["success"]:
        # Combined timetable includes fixed civil schedule and any course-level pinned sessions
        combined = list(scheduler.fixed_schedule) + list(result["schedule"])
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
    swap_entry_id = body.get("swap_entry_id")

    tt = data.get("timetable", [])
    entry = next((e for e in tt if e.get("id") == entry_id), None)
    if not entry:
        return jsonify({"success": False, "message": "Entry not found"}), 404

    days_list = data["config"].get("days", [])
    periods_list = data["config"].get("periods", [])

    if swap_entry_id:
        swap_entry = next((e for e in tt if e.get("id") == swap_entry_id), None)
        if not swap_entry:
            return jsonify({"success": False, "message": "Swap target entry not found"}), 404

        # Swap positions between entry and swap_entry
        orig_day = entry["day"]
        orig_period = entry["period"]

        entry["day"] = swap_entry["day"]
        entry["period"] = swap_entry["period"]
        entry["day_name"] = swap_entry.get("day_name")
        entry["period_name"] = swap_entry.get("period_name")
        entry["period_time"] = swap_entry.get("period_time")

        swap_entry["day"] = orig_day
        swap_entry["period"] = orig_period
        swap_entry["day_name"] = days_list[orig_day] if orig_day < len(days_list) else f"Day {orig_day+1}"
        if orig_period < len(periods_list):
            swap_entry["period_name"] = periods_list[orig_period].get("name")
            swap_entry["period_time"] = periods_list[orig_period].get("time")

        import time
        data["_last_modified"] = int(time.time() * 1000)
        save_data(data)
        return jsonify({
            "success": True,
            "action": "swap",
            "message": f"Successfully swapped {entry.get('course_code')} and {swap_entry.get('course_code')}",
            "timetable": tt,
            "_last_modified": data["_last_modified"]
        })

    # Standard Move
    entry["day"] = target_day
    entry["day_name"] = days_list[target_day] if target_day < len(days_list) else f"Day {target_day+1}"
    entry["period"] = target_period
    
    # Update period name and time
    if target_period < len(periods_list):
        entry["period_name"] = periods_list[target_period].get("name")
        entry["period_time"] = periods_list[target_period].get("time")

    if target_room_id:
        room_obj = next((r for r in data.get("rooms", []) if r["id"] == target_room_id), None)
        if room_obj:
            entry["room_id"] = room_obj["id"]
            entry["room_name"] = room_obj["name"]

    import time
    data["_last_modified"] = int(time.time() * 1000)
    save_data(data)
    return jsonify({
        "success": True,
        "action": "move",
        "message": f"Successfully moved {entry.get('course_code')} to {entry.get('day_name')} {entry.get('period_name')}",
        "timetable": tt,
        "_last_modified": data["_last_modified"]
    })

@app.route('/api/export/csv', methods=['GET'])
def export_csv():
    data = load_data()
    sync_fixed_schedule_teachers(data)
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

@app.route('/api/export/excel', methods=['GET'])
def export_excel():
    data = load_data()
    sem_type = request.args.get("semester", data.get("config", {}).get("semester", "Even Semester"))
    sync_fixed_schedule_teachers(data, sem_type)
    excel_stream = exporter.generate_excel(data, sem_type)
    sem_slug = "even" if "Even" in str(sem_type) else "odd"
    filename = f"civil_timetable_{sem_slug}_2026_27.xlsx"
    return send_file(
        excel_stream,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename
    )

@app.route('/api/export/pdf/class', methods=['GET'])
def export_class_pdf():
    data = load_data()
    sem_type = request.args.get("semester", data.get("config", {}).get("semester", "Even Semester"))
    sync_fixed_schedule_teachers(data, sem_type)
    pdf_stream = exporter.generate_class_pdf(data, sem_type)
    sem_slug = "even" if "Even" in str(sem_type) else "odd"
    filename = f"civil_class_timetable_{sem_slug}_2026_27.pdf"
    return send_file(
        pdf_stream,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename
    )

@app.route('/api/export/pdf/faculty', methods=['GET'])
def export_faculty_pdf():
    data = load_data()
    sem_type = request.args.get("semester", data.get("config", {}).get("semester", "Even Semester"))
    sync_fixed_schedule_teachers(data, sem_type)
    pdf_stream = exporter.generate_faculty_pdf(data, sem_type)
    sem_slug = "even" if "Even" in str(sem_type) else "odd"
    filename = f"civil_faculty_timetable_{sem_slug}_2026_27.pdf"
    return send_file(
        pdf_stream,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename
    )

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    print(f"* Curriculum Scheduler running on http://127.0.0.1:{port}")
    app.run(host='0.0.0.0', port=port, debug=True)
