import os
import json
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from scheduler import TimetableScheduler

app = Flask(__name__, static_folder='static', static_url_path='')
CORS(app)

DATA_FILE = os.path.join(os.path.dirname(__file__), 'timetable_data.json')

DEFAULT_SAMPLE_DATA = {
    "config": {
        "title": "Department of Civil Engineering - Master Timetable",
        "academic_year": "2026-2027",
        "semester": "Even Semester",
        "days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
        "periods_per_day": 6,
        "recess_after_period": 4, # Lunch Break is 1:00 PM - 2:00 PM (after Period 4)
        "period_times": [
            "09:00 - 10:00",
            "10:00 - 11:00",
            "11:00 - 12:00",
            "12:00 - 01:00",
            "02:00 - 03:00",
            "03:00 - 04:00"
        ],
        "saturday_max_period": 4 # Saturday classes run till 1:00 PM only
    },
    "departments": [
        {"id": "dept_civil", "name": "Civil Engineering"}
    ],
    "faculty": [
        {"id": "f_1", "name": "Prof. Adarsh S V", "code": "AS", "designation": "Assistant Professor", "email": "adarsh.sv@christuniversity.in", "unavailable_slots": []},
        {"id": "f_2", "name": "Dr. Aniket Bhalkikar", "code": "AB", "designation": "Assistant Professor", "email": "aniket.bhalkikar@christuniversity.in", "unavailable_slots": []},
        {"id": "f_3", "name": "Dr. Arpan Pradhan", "code": "AP", "designation": "Assistant Professor", "email": "arpan.pradhan@christuniversity.in", "unavailable_slots": []},
        {"id": "f_4", "name": "Dr. Beulah M", "code": "BM", "designation": "Associate Professor", "email": "beulah.m@christuniversity.in", "unavailable_slots": []},
        {"id": "f_5", "name": "Dr. Hossiney Nabil Jalall", "code": "NH", "designation": "Associate Professor", "email": "nabil.hossiney@christuniversity.in", "unavailable_slots": []},
        {"id": "f_6", "name": "Dr. Jacob Alex Kollerathu", "code": "JA", "designation": "Assistant Professor", "email": "jacob.alex@christuniversity.in", "unavailable_slots": []},
        {"id": "f_7", "name": "Dr. Laxmi", "code": "LX", "designation": "Assistant Professor", "email": "laxmi@christuniversity.in", "unavailable_slots": []},
        {"id": "f_8", "name": "Dr. Sarath Chandra K", "code": "SC", "designation": "Associate Professor", "email": "sarath.chandra@christuniversity.in", "unavailable_slots": []},
        {"id": "f_9", "name": "Dr. Shibu K Mani", "code": "SM", "designation": "Professor", "email": "shibu.mani@christuniversity.in", "unavailable_slots": []},
        {"id": "f_10", "name": "Dr. Srinidhi Lakshmish K", "code": "SL", "designation": "Assistant Professor", "email": "srinidhi.kumar@christuniversity.in", "unavailable_slots": []},
        {"id": "f_11", "name": "Dr. Sujatha Unnikrishnan", "code": "SU", "designation": "Associate Professor & HoD", "email": "sujatha.unnikrishnan@christuniversity.in", "unavailable_slots": []},
        {"id": "f_12", "name": "Dr. Thejas H K", "code": "TH", "designation": "Assistant Professor", "email": "thejas.hk@christuniversity.in", "unavailable_slots": []},
        {"id": "f_13", "name": "Dr. Tom Damion", "code": "TD", "designation": "Assistant Professor", "email": "tom.damion@christuniversity.in", "unavailable_slots": []},
        {"id": "f_14", "name": "Dr. Uppaluri Sirisha", "code": "US", "designation": "Associate Professor", "email": "sirisha.uppaluri@christuniversity.in", "unavailable_slots": []},
        {"id": "f_15", "name": "Prof. Yogeshraj Urs C", "code": "YU", "designation": "Assistant Professor", "email": "yogeshraj.urs@christuniversity.in", "unavailable_slots": []}
    ],
    "batches": [
        {"id": "b_4btci", "name": "4BTCI (4th Sem Civil)", "department_id": "dept_civil"},
        {"id": "b_6btci", "name": "6BTCI (6th Sem Civil)", "department_id": "dept_civil"},
        {"id": "b_8btci", "name": "8BTCI (8th Sem Civil)", "department_id": "dept_civil"},
        {"id": "b_1barc_a", "name": "1BARC - A (Architecture)", "department_id": "dept_arch"},
        {"id": "b_1barc_b", "name": "1BARC - B (Architecture)", "department_id": "dept_arch"},
        {"id": "b_2barc_a", "name": "2BARC - A (Architecture)", "department_id": "dept_arch"},
        {"id": "b_2barc_b", "name": "2BARC - B (Architecture)", "department_id": "dept_arch"},
        {"id": "b_3barc_a", "name": "3BARC - A (Architecture)", "department_id": "dept_arch"},
        {"id": "b_3barc_b", "name": "3BARC - B (Architecture)", "department_id": "dept_arch"},
        {"id": "b_phy_a", "name": "1BTPHY A (1st Year)", "department_id": "dept_basic"},
        {"id": "b_phy_b", "name": "1BTPHY B (1st Year)", "department_id": "dept_basic"},
        {"id": "b_phy_c", "name": "1BTPHY C (1st Year)", "department_id": "dept_basic"},
        {"id": "b_phy_d", "name": "1BTPHY D (1st Year)", "department_id": "dept_basic"},
        {"id": "b_phy_e", "name": "1BTPHY E (1st Year)", "department_id": "dept_basic"},
        {"id": "b_phy_f", "name": "1BTPHY F (1st Year)", "department_id": "dept_basic"},
        {"id": "b_phy_g", "name": "1BTPHY G (1st Year)", "department_id": "dept_basic"},
        {"id": "b_phy_h", "name": "1BTPHY H (1st Year)", "department_id": "dept_basic"}
    ],
    "rooms": [
        {"id": "r_lh1", "name": "Civil Lecture Hall 1", "type": "Lecture", "capacity": 60},
        {"id": "r_lh2", "name": "Civil Lecture Hall 2", "type": "Lecture", "capacity": 60},
        {"id": "r_lh3", "name": "Civil Lecture Hall 3", "type": "Lecture", "capacity": 60},
        {"id": "r_hyd_lab", "name": "Hydraulics Engineering Lab", "type": "Lab", "capacity": 30},
        {"id": "r_geo_lab", "name": "Geotechnical Engineering Lab", "type": "Lab", "capacity": 30},
        {"id": "r_cad_lab", "name": "CADD / Computing Lab", "type": "Lab", "capacity": 60},
        {"id": "r_sur_lab", "name": "Surveying Lab", "type": "Lab", "capacity": 30},
        {"id": "r_mt_lab", "name": "Materials / Concrete Testing Lab", "type": "Lab", "capacity": 30}
    ],
    "unmapped_subjects": [
        # 4BTCI (4th Sem Civil)
        {"id": "s_ce431", "code": "CE431", "name": "Structural Analysis I", "batch_id": "b_4btci", "weekly_periods": 4, "is_lab": False, "block_size": 1, "room_type": "Lecture"},
        {"id": "s_ce432p_th", "code": "CE432P", "name": "Hydraulics Engineering (Theory)", "batch_id": "b_4btci", "weekly_periods": 4, "is_lab": False, "block_size": 1, "room_type": "Lecture"},
        {"id": "s_ce432p_lab", "code": "CE432P-LAB", "name": "Hydraulics Engineering Lab", "batch_id": "b_4btci", "weekly_periods": 2, "is_lab": True, "block_size": 2, "room_type": "Lab"},
        {"id": "s_ce433p_th", "code": "CE433P", "name": "Geotechnical Engineering I (Theory)", "batch_id": "b_4btci", "weekly_periods": 3, "is_lab": False, "block_size": 1, "room_type": "Lecture"},
        {"id": "s_ce433p_lab", "code": "CE433P-LAB", "name": "Geotechnical Engineering I Lab", "batch_id": "b_4btci", "weekly_periods": 2, "is_lab": True, "block_size": 2, "room_type": "Lab"},
        {"id": "s_ce434", "code": "CE434", "name": "Transportation Engineering", "batch_id": "b_4btci", "weekly_periods": 4, "is_lab": False, "block_size": 1, "room_type": "Lecture"},
        {"id": "s_ce451", "code": "CE451", "name": "CADD Lab", "batch_id": "b_4btci", "weekly_periods": 4, "is_lab": True, "block_size": 2, "room_type": "Lab"},
        {"id": "s_hs423", "code": "HS423", "name": "Professional Ethics", "batch_id": "b_4btci", "weekly_periods": 2, "is_lab": False, "block_size": 1, "room_type": "Lecture"},
        {"id": "s_btoe461", "code": "BTOE461", "name": "L & T Track 1/3", "batch_id": "b_4btci", "weekly_periods": 2, "is_lab": False, "block_size": 1, "room_type": "Lecture"},
        {"id": "s_oec472", "code": "OEC472", "name": "Ability Enhancement Course", "batch_id": "b_4btci", "weekly_periods": 2, "is_lab": False, "block_size": 1, "room_type": "Lecture"},

        # 6BTCI (6th Sem Civil)
        {"id": "s_ce631", "code": "CE631", "name": "Quantity Surveying and Cost Estimation", "batch_id": "b_6btci", "weekly_periods": 4, "is_lab": False, "block_size": 1, "room_type": "Lecture"},
        {"id": "s_ce632", "code": "CE632", "name": "Design of Steel Structures", "batch_id": "b_6btci", "weekly_periods": 4, "is_lab": False, "block_size": 1, "room_type": "Lecture"},
        {"id": "s_ce633", "code": "CE633", "name": "Hydrology and Water Resources Engineering", "batch_id": "b_6btci", "weekly_periods": 4, "is_lab": False, "block_size": 1, "room_type": "Lecture"},
        {"id": "s_ce634", "code": "CE634", "name": "Disaster Preparedness and Planning", "batch_id": "b_6btci", "weekly_periods": 2, "is_lab": False, "block_size": 1, "room_type": "Lecture"},
        {"id": "s_ce651", "code": "CE651", "name": "Extensive Surveying Camp", "batch_id": "b_6btci", "weekly_periods": 2, "is_lab": True, "block_size": 2, "room_type": "Lab"},
        {"id": "s_ce652", "code": "CE652", "name": "Field Practice", "batch_id": "b_6btci", "weekly_periods": 2, "is_lab": True, "block_size": 2, "room_type": "Lab"},
        {"id": "s_ce681", "code": "CE681", "name": "Service Learning", "batch_id": "b_6btci", "weekly_periods": 2, "is_lab": True, "block_size": 2, "room_type": "Lab"},
        {"id": "s_ce671", "code": "CE671", "name": "Ability Enhancement Course", "batch_id": "b_6btci", "weekly_periods": 2, "is_lab": False, "block_size": 1, "room_type": "Lecture"},
        {"id": "s_cc_tue", "code": "CC-TUE", "name": "Certificate Course (Tuesday)", "batch_id": "b_6btci", "weekly_periods": 2, "is_lab": True, "block_size": 2, "room_type": "Lab"},
        {"id": "s_cc_fri", "code": "CC-FRI", "name": "Certificate Course (Friday)", "batch_id": "b_6btci", "weekly_periods": 2, "is_lab": True, "block_size": 2, "room_type": "Lab"},

        # Architecture Courses
        {"id": "s_arc232_a", "code": "ARC232-A", "name": "Logic of Structures - II (Sec A)", "batch_id": "b_1barc_a", "weekly_periods": 3, "is_lab": False, "block_size": 1, "room_type": "Lecture"},
        {"id": "s_arc232_b", "code": "ARC232-B", "name": "Logic of Structures - II (Sec B)", "batch_id": "b_1barc_b", "weekly_periods": 3, "is_lab": False, "block_size": 1, "room_type": "Lecture"},
        {"id": "s_arc432_a", "code": "ARC432-A", "name": "Logic of Structures - IV (Sec A)", "batch_id": "b_2barc_a", "weekly_periods": 3, "is_lab": False, "block_size": 1, "room_type": "Lecture"},
        {"id": "s_arc432_b", "code": "ARC432-B", "name": "Logic of Structures - IV (Sec B)", "batch_id": "b_2barc_b", "weekly_periods": 3, "is_lab": False, "block_size": 1, "room_type": "Lecture"},
        {"id": "s_arc631_a", "code": "ARC631-A", "name": "Specification & Estimation (Sec A)", "batch_id": "b_3barc_a", "weekly_periods": 3, "is_lab": False, "block_size": 1, "room_type": "Lecture"},
        {"id": "s_arc631_b", "code": "ARC631-B", "name": "Specification & Estimation (Sec B)", "batch_id": "b_3barc_b", "weekly_periods": 3, "is_lab": False, "block_size": 1, "room_type": "Lecture"},

        # Environmental Science
        {"id": "s_evs_ai", "code": "EVS321-AI", "name": "Environmental Science (3BTAI)", "batch_id": "b_evs_ai", "weekly_periods": 2, "is_lab": False, "block_size": 1, "room_type": "Lecture"},
        {"id": "s_evs_aiml_a", "code": "EVS321-AIML-A", "name": "Environmental Science (AIML A)", "batch_id": "b_evs_aiml_a", "weekly_periods": 2, "is_lab": False, "block_size": 1, "room_type": "Lecture"},
        {"id": "s_evs_aiml_bc", "code": "EVS321-AIML-BC", "name": "Environmental Science (AIML B & C)", "batch_id": "b_evs_aiml_bc", "weekly_periods": 2, "is_lab": False, "block_size": 1, "room_type": "Lecture"},
        {"id": "s_evs_ds", "code": "EVS321-DS", "name": "Environmental Science (DS)", "batch_id": "b_evs_ds", "weekly_periods": 2, "is_lab": False, "block_size": 1, "room_type": "Lecture"}
    ],
    # Fixed Basics of Civil Engg (CE 234P) slots locked as hard schedule entries
    "fixed_ce234p_schedule": [
        # 1BTPHY A
        {"day": 1, "day_name": "Tuesday", "period": 1, "period_time": "10:00 - 11:00", "batch_name": "1BTPHY A", "course_code": "CE 234P", "course_name": "Basics of Civil & Mech", "is_lab": False},
        {"day": 2, "day_name": "Wednesday", "period": 1, "period_time": "10:00 - 11:00", "batch_name": "1BTPHY A", "course_code": "CE 234P-LAB", "course_name": "Basics of Civil Lab", "is_lab": True},
        {"day": 2, "day_name": "Wednesday", "period": 2, "period_time": "11:00 - 12:00", "batch_name": "1BTPHY A", "course_code": "CE 234P-LAB", "course_name": "Basics of Civil Lab", "is_lab": True},
        {"day": 2, "day_name": "Wednesday", "period": 5, "period_time": "03:00 - 04:00", "batch_name": "1BTPHY A", "course_code": "CE 234P", "course_name": "Basics of Civil & Mech", "is_lab": False},
        {"day": 4, "day_name": "Friday", "period": 1, "period_time": "10:00 - 11:00", "batch_name": "1BTPHY A", "course_code": "CE 234P", "course_name": "Basics of Civil & Mech", "is_lab": False},
        {"day": 5, "day_name": "Saturday", "period": 0, "period_time": "09:00 - 10:00", "batch_name": "1BTPHY A", "course_code": "CE 234P", "course_name": "Basics of Civil & Mech", "is_lab": False},

        # 1BTPHY B
        {"day": 0, "day_name": "Monday", "period": 3, "period_time": "12:00 - 01:00", "batch_name": "1BTPHY B", "course_code": "CE 234P", "course_name": "Basics of Civil & Mech", "is_lab": False},
        {"day": 2, "day_name": "Wednesday", "period": 5, "period_time": "03:00 - 04:00", "batch_name": "1BTPHY B", "course_code": "CE 234P", "course_name": "Basics of Civil & Mech", "is_lab": False},
        {"day": 4, "day_name": "Friday", "period": 0, "period_time": "09:00 - 10:00", "batch_name": "1BTPHY B", "course_code": "CE 234P", "course_name": "Basics of Civil & Mech", "is_lab": False},
        {"day": 4, "day_name": "Friday", "period": 2, "period_time": "11:00 - 12:00", "batch_name": "1BTPHY B", "course_code": "CE 234P-LAB", "course_name": "Basics of Civil Lab", "is_lab": True},
        {"day": 4, "day_name": "Friday", "period": 3, "period_time": "12:00 - 01:00", "batch_name": "1BTPHY B", "course_code": "CE 234P-LAB", "course_name": "Basics of Civil Lab", "is_lab": True},
        {"day": 5, "day_name": "Saturday", "period": 1, "period_time": "10:00 - 11:00", "batch_name": "1BTPHY B", "course_code": "CE 234P", "course_name": "Basics of Civil & Mech", "is_lab": False},

        # 1BTPHY C
        {"day": 0, "day_name": "Monday", "period": 4, "period_time": "02:00 - 03:00", "batch_name": "1BTPHY C", "course_code": "CE 234P-LAB", "course_name": "Basics of Civil Lab", "is_lab": True},
        {"day": 0, "day_name": "Monday", "period": 5, "period_time": "03:00 - 04:00", "batch_name": "1BTPHY C", "course_code": "CE 234P-LAB", "course_name": "Basics of Civil Lab", "is_lab": True},
        {"day": 1, "day_name": "Tuesday", "period": 5, "period_time": "03:00 - 04:00", "batch_name": "1BTPHY C", "course_code": "CE 234P", "course_name": "Basics of Civil & Mech", "is_lab": False},
        {"day": 3, "day_name": "Thursday", "period": 4, "period_time": "02:00 - 03:00", "batch_name": "1BTPHY C", "course_code": "CE 234P", "course_name": "Basics of Civil & Mech", "is_lab": False},
        {"day": 4, "day_name": "Friday", "period": 1, "period_time": "10:00 - 11:00", "batch_name": "1BTPHY C", "course_code": "CE 234P", "course_name": "Basics of Civil & Mech", "is_lab": False},
        {"day": 5, "day_name": "Saturday", "period": 3, "period_time": "12:00 - 01:00", "batch_name": "1BTPHY C", "course_code": "CE 234P", "course_name": "Basics of Civil & Mech", "is_lab": False},

        # 1BTPHY D
        {"day": 0, "day_name": "Monday", "period": 0, "period_time": "09:00 - 10:00", "batch_name": "1BTPHY D", "course_code": "CE 234P", "course_name": "Basics of Civil & Mech", "is_lab": False},
        {"day": 2, "day_name": "Wednesday", "period": 5, "period_time": "03:00 - 04:00", "batch_name": "1BTPHY D", "course_code": "CE 234P", "course_name": "Basics of Civil & Mech", "is_lab": False},
        {"day": 3, "day_name": "Thursday", "period": 0, "period_time": "09:00 - 10:00", "batch_name": "1BTPHY D", "course_code": "CE 234P", "course_name": "Basics of Civil & Mech", "is_lab": False},
        {"day": 3, "day_name": "Thursday", "period": 2, "period_time": "11:00 - 12:00", "batch_name": "1BTPHY D", "course_code": "CE 234P-LAB", "course_name": "Basics of Civil Lab", "is_lab": True},
        {"day": 3, "day_name": "Thursday", "period": 3, "period_time": "12:00 - 01:00", "batch_name": "1BTPHY D", "course_code": "CE 234P-LAB", "course_name": "Basics of Civil Lab", "is_lab": True},
        {"day": 5, "day_name": "Saturday", "period": 1, "period_time": "10:00 - 11:00", "batch_name": "1BTPHY D", "course_code": "CE 234P", "course_name": "Basics of Civil & Mech", "is_lab": False},

        # 1BTPHY E
        {"day": 1, "day_name": "Tuesday", "period": 5, "period_time": "03:00 - 04:00", "batch_name": "1BTPHY E", "course_code": "CE 234P", "course_name": "Basics of Civil & Mech", "is_lab": False},
        {"day": 2, "day_name": "Wednesday", "period": 0, "period_time": "09:00 - 10:00", "batch_name": "1BTPHY E", "course_code": "CE 234P", "course_name": "Basics of Civil & Mech", "is_lab": False},
        {"day": 3, "day_name": "Thursday", "period": 2, "period_time": "11:00 - 12:00", "batch_name": "1BTPHY E", "course_code": "CE 234P", "course_name": "Basics of Civil & Mech", "is_lab": False},
        {"day": 4, "day_name": "Friday", "period": 4, "period_time": "02:00 - 03:00", "batch_name": "1BTPHY E", "course_code": "CE 234P-LAB", "course_name": "Basics of Civil Lab", "is_lab": True},
        {"day": 4, "day_name": "Friday", "period": 5, "period_time": "03:00 - 04:00", "batch_name": "1BTPHY E", "course_code": "CE 234P-LAB", "course_name": "Basics of Civil Lab", "is_lab": True},
        {"day": 5, "day_name": "Saturday", "period": 0, "period_time": "09:00 - 10:00", "batch_name": "1BTPHY E", "course_code": "CE 234P", "course_name": "Basics of Civil & Mech", "is_lab": False},

        # 1BTPHY F
        {"day": 0, "day_name": "Monday", "period": 4, "period_time": "02:00 - 03:00", "batch_name": "1BTPHY F", "course_code": "CE 234P", "course_name": "Basics of Civil & Mech", "is_lab": False},
        {"day": 1, "day_name": "Tuesday", "period": 4, "period_time": "02:00 - 03:00", "batch_name": "1BTPHY F", "course_code": "CE 234P", "course_name": "Basics of Civil & Mech", "is_lab": False},
        {"day": 3, "day_name": "Thursday", "period": 1, "period_time": "10:00 - 11:00", "batch_name": "1BTPHY F", "course_code": "CE 234P", "course_name": "Basics of Civil & Mech", "is_lab": False},
        {"day": 3, "day_name": "Thursday", "period": 4, "period_time": "02:00 - 03:00", "batch_name": "1BTPHY F", "course_code": "CE 234P-LAB", "course_name": "Basics of Civil Lab", "is_lab": True},
        {"day": 3, "day_name": "Thursday", "period": 5, "period_time": "03:00 - 04:00", "batch_name": "1BTPHY F", "course_code": "CE 234P-LAB", "course_name": "Basics of Civil Lab", "is_lab": True},
        {"day": 5, "day_name": "Saturday", "period": 0, "period_time": "09:00 - 10:00", "batch_name": "1BTPHY F", "course_code": "CE 234P", "course_name": "Basics of Civil & Mech", "is_lab": False},

        # 1BTPHY G
        {"day": 0, "day_name": "Monday", "period": 0, "period_time": "09:00 - 10:00", "batch_name": "1BTPHY G", "course_code": "CE 234P-LAB", "course_name": "Basics of Civil Lab", "is_lab": True},
        {"day": 0, "day_name": "Monday", "period": 1, "period_time": "10:00 - 11:00", "batch_name": "1BTPHY G", "course_code": "CE 234P-LAB", "course_name": "Basics of Civil Lab", "is_lab": True},
        {"day": 0, "day_name": "Monday", "period": 3, "period_time": "12:00 - 01:00", "batch_name": "1BTPHY G", "course_code": "CE 234P", "course_name": "Basics of Civil & Mech", "is_lab": False},
        {"day": 3, "day_name": "Thursday", "period": 4, "period_time": "02:00 - 03:00", "batch_name": "1BTPHY G", "course_code": "CE 234P", "course_name": "Basics of Civil & Mech", "is_lab": False},
        {"day": 4, "day_name": "Friday", "period": 2, "period_time": "11:00 - 12:00", "batch_name": "1BTPHY G", "course_code": "CE 234P", "course_name": "Basics of Civil & Mech", "is_lab": False},
        {"day": 5, "day_name": "Saturday", "period": 2, "period_time": "11:00 - 12:00", "batch_name": "1BTPHY G", "course_code": "CE 234P", "course_name": "Basics of Civil & Mech", "is_lab": False},

        # 1BTPHY H
        {"day": 0, "day_name": "Monday", "period": 5, "period_time": "03:00 - 04:00", "batch_name": "1BTPHY H", "course_code": "CE 234P", "course_name": "Basics of Civil & Mech", "is_lab": False},
        {"day": 1, "day_name": "Tuesday", "period": 4, "period_time": "02:00 - 03:00", "batch_name": "1BTPHY H", "course_code": "CE 234P-LAB", "course_name": "Basics of Civil Lab", "is_lab": True},
        {"day": 1, "day_name": "Tuesday", "period": 5, "period_time": "03:00 - 04:00", "batch_name": "1BTPHY H", "course_code": "CE 234P-LAB", "course_name": "Basics of Civil Lab", "is_lab": True},
        {"day": 3, "day_name": "Thursday", "period": 2, "period_time": "11:00 - 12:00", "batch_name": "1BTPHY H", "course_code": "CE 234P", "course_name": "Basics of Civil & Mech", "is_lab": False},
        {"day": 4, "day_name": "Friday", "period": 2, "period_time": "11:00 - 12:00", "batch_name": "1BTPHY H", "course_code": "CE 234P", "course_name": "Basics of Civil & Mech", "is_lab": False},
        {"day": 5, "day_name": "Saturday", "period": 3, "period_time": "12:00 - 01:00", "batch_name": "1BTPHY H", "course_code": "CE 234P", "course_name": "Basics of Civil & Mech", "is_lab": False}
    ],
    "courses": [], # Empty by default so you can map faculty to courses yourself!
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
        data.update(req_body)
        save_data(data)

    config = data.get("config", {})
    teachers = data.get("faculty", [])
    rooms = data.get("rooms", [])
    batches = data.get("batches", [])
    courses = data.get("courses", [])

    scheduler = TimetableScheduler(config, teachers, rooms, batches, courses)
    result = scheduler.generate(max_attempts=100)

    if result["success"]:
        # Prepend the fixed Basics of Civil Engineering slots
        combined = list(data.get("fixed_ce234p_schedule", [])) + result["schedule"]
        data["timetable"] = combined
        save_data(data)
        result["schedule"] = combined

    return jsonify(result)

@app.route('/api/export/csv', methods=['GET'])
def export_csv():
    data = load_data()
    tt = data.get("timetable", [])
    if not tt:
        tt = data.get("fixed_ce234p_schedule", [])
    
    rows = ["Day,Period,Timing,Batch,Course Code,Course Name,Faculty,Room,Is Lab"]
    for e in sorted(tt, key=lambda x: (x.get('batch_name', ''), x.get('day', 0), x.get('period', 0))):
        rows.append(f'"{e.get("day_name","")}","{e.get("period",0)+1}","{e.get("period_time","")}","{e.get("batch_name","")}","{e.get("course_code","")}","{e.get("course_name","")}","{e.get("teacher_name","TBD")}","{e.get("room_name","")}","{e.get("is_lab",False)}"')
    
    csv_text = "\n".join(rows)
    return csv_text, 200, {
        'Content-Type': 'text/csv; charset=utf-8',
        'Content-Disposition': 'attachment; filename="civil_timetable_2026_27.csv"'
    }

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    print(f"🚀 Timetable Portal running on http://127.0.0.1:{port}")
    app.run(host='0.0.0.0', port=port, debug=True)
