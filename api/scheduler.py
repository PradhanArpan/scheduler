import random
from copy import deepcopy

class TimetableScheduler:
    def __init__(self, config, teachers, rooms, batches, courses, sub_batches=None, fixed_schedule=None):
        self.config = config
        self.fixed_schedule = fixed_schedule or []
        self.days = config.get("days", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"])
        self.num_days = len(self.days)
        
        # Support rich periods or fallback
        if "periods" in config and config["periods"]:
            self.periods = config["periods"]
        else:
            p_times = config.get("period_times", ["09:00 - 10:00", "10:00 - 11:00", "11:00 - 12:00", "12:00 - 01:00", "02:00 - 03:00", "03:00 - 04:00"])
            recess_after = config.get("recess_after_period", 4)
            self.periods = []
            for idx, pt in enumerate(p_times):
                self.periods.append({"id": f"p{idx+1}", "name": f"Period {idx+1}", "time": pt, "is_break": False})
                if idx + 1 == recess_after:
                    self.periods.append({"id": "lunch", "name": "Lunch Break", "time": "01:00 - 02:00", "is_break": True})

        self.periods_count = len(self.periods)
        self.teaching_period_indices = [i for i, p in enumerate(self.periods) if not p.get("is_break", False)]
        self.break_period_indices = set(i for i, p in enumerate(self.periods) if p.get("is_break", False))
        
        # Inactive slots (e.g. Saturday afternoon, custom matrix)
        self.inactive_slots = set()
        saturday_idx = 5 if self.num_days >= 6 else -1
        sat_max = config.get("saturday_max_period", 4)
        if saturday_idx >= 0 and sat_max is not None:
            teaching_seen = 0
            for idx, p in enumerate(self.periods):
                if not p.get("is_break"):
                    teaching_seen += 1
                    if teaching_seen > sat_max:
                        self.inactive_slots.add((saturday_idx, idx))
                else:
                    if teaching_seen >= sat_max:
                        self.inactive_slots.add((saturday_idx, idx))

        if "day_working_matrix" in config:
            for d_str, slot_flags in config["day_working_matrix"].items():
                d = int(d_str)
                for p_idx, is_active in enumerate(slot_flags):
                    if not is_active:
                        self.inactive_slots.add((d, p_idx))

        # Advanced constraints configuration with FET Confidence Weights (0% - 100%)
        adv = config.get("advanced_constraints", {})
        self.faculty_max_hours_per_day = adv.get("faculty_max_hours_per_day", 4)
        self.max_daily_weight = adv.get("max_daily_weight", 95)
        
        self.faculty_no_consecutive = adv.get("faculty_no_consecutive", True)
        self.faculty_no_consecutive_theory = adv.get("faculty_no_consecutive_theory", True)
        self.faculty_max_consecutive_hours = adv.get("faculty_max_consecutive_hours", 2)
        self.consecutive_weight = adv.get("consecutive_weight", 95)
        
        self.single_theory_per_day_per_course = adv.get("single_theory_per_day_per_course", True)
        
        self.theory_on_first_hour = adv.get("theory_on_first_hour", True)
        self.theory_1st_weight = adv.get("theory_1st_weight", 95)
        
        self.no_fourth_hour_free = adv.get("no_fourth_hour_free", True)
        self.prime_hours_weight = adv.get("prime_hours_weight", 90)
        
        self.faculty_guarantee_free_day = adv.get("faculty_guarantee_free_day", True)
        self.free_day_weight = adv.get("free_day_weight", 95)
        
        self.distribute_sessions_evenly = adv.get("distribute_sessions_evenly", True)
        self.even_dist_weight = adv.get("even_dist_weight", 85)
        
        # Meeting slots: (day, period) - applies to all faculty
        self.meeting_slots = set()
        for m in adv.get("department_meetings", []):
            self.meeting_slots.add((m.get("day"), m.get("period")))
            
        # Batch-specific blocked slots: (batch_id, day, period)
        self.batch_blocked = set()
        for b_b in adv.get("batch_blocked_slots", []):
            self.batch_blocked.add((b_b.get("batch_id"), b_b.get("day"), b_b.get("period")))

        self.teachers = {t["id"]: t for t in teachers}
        self.rooms = {r["id"]: r for r in rooms}
        # Add legacy room aliases for backward compatibility
        alias_map = {'r_lh_101': 'r_lh1', 'r_lh_102': 'r_lh2', 'r_lh_103': 'r_lh3'}
        for old_id, new_id in alias_map.items():
            if new_id in self.rooms and old_id not in self.rooms:
                self.rooms[old_id] = self.rooms[new_id]
        self.batches = {b["id"]: b for b in batches}
        self.sub_batches = {sb["id"]: sb for sb in (sub_batches or [])}
        self.courses = courses

        # Incorporate course-level pinned/fixed sessions into self.fixed_schedule
        for c in self.courses:
            for fs in c.get("fixed_slots", []):
                day = fs.get("day")
                period = fs.get("period")
                if day is not None and period is not None:
                    t_ids = fs.get("teacher_ids") or c.get("teacher_ids") or ([c["teacher_id"]] if c.get("teacher_id") else [])
                    t_ids = [tid for tid in t_ids if tid]
                    r_id = fs.get("room_id") or c.get("preferred_room_id")
                    b_id = c.get("batch_id")
                    if not r_id and b_id:
                        r_id = self.batches.get(b_id, {}).get("default_room_id")
                    
                    names = [self.teachers[tid]["name"] for tid in t_ids if tid in self.teachers]
                    codes = [self.teachers[tid]["code"] for tid in t_ids if tid in self.teachers]
                    t_name_str = " & ".join(names) if names else "TBD"
                    t_code_str = "/".join(codes) if codes else ""
                    
                    period_obj = self.periods[period] if period < len(self.periods) else {"name": f"Period {period+1}", "time": ""}
                    b_name = self.batches.get(b_id, {}).get("name", "")
                    sb_name = self.sub_batches.get(c.get("sub_batch_id"), {}).get("name", "")
                    r_name = self.rooms.get(r_id, {}).get("name", "")
                    
                    fixed_entry = {
                        "id": f"pinned_{c['id']}_d{day}_p{period}",
                        "day": day,
                        "day_name": self.days[day] if day < len(self.days) else f"Day {day+1}",
                        "period": period,
                        "period_name": period_obj.get("name"),
                        "period_time": period_obj.get("time"),
                        "course_id": c["id"],
                        "course_name": c.get("name"),
                        "course_code": c.get("code"),
                        "teacher_id": t_ids[0] if t_ids else "",
                        "teacher_ids": t_ids,
                        "teacher_name": t_name_str,
                        "teacher_code": t_code_str,
                        "batch_id": b_id,
                        "batch_name": b_name,
                        "sub_batch_id": c.get("sub_batch_id"),
                        "sub_batch_name": sb_name,
                        "room_id": r_id,
                        "room_name": r_name,
                        "is_lab": c.get("is_lab", False),
                        "is_pinned": True
                    }
                    if not any(f.get("batch_id") == b_id and f.get("day") == day and f.get("period") == period for f in self.fixed_schedule):
                        self.fixed_schedule.append(fixed_entry)

    def pre_check_feasibility(self):
        """
        Pre-flight validation: Checks capacity, over-allocation,
        and hard impossibilities before running solver.
        """
        errors = []
        warnings = []

        total_teaching_periods = len(self.teaching_period_indices)
        teaching_inactive_count = sum(1 for (d, p) in self.inactive_slots if p in self.teaching_period_indices)
        total_week_slots = self.num_days * total_teaching_periods - teaching_inactive_count

        # 1. Batch slot capacity check
        batch_demand = {}
        for c in self.courses:
            b_id = c.get("batch_id")
            if b_id:
                batch_demand[b_id] = batch_demand.get(b_id, 0) + c.get("weekly_periods", 0)

        for b_id, demand in batch_demand.items():
            b_name = self.batches.get(b_id, {}).get("name", b_id)
            # count batch blocked slots and unavailable slots
            blocked_count = sum(1 for (b, d, p) in self.batch_blocked if b == b_id)
            unavail_count = len(self.batches.get(b_id, {}).get("unavailable_slots", []))
            available = total_week_slots - blocked_count - unavail_count
            if demand > available:
                errors.append(f"Batch '{b_name}' requires {demand} periods/week, but only {available} slots are available (Deficit: {demand - available}).")
            elif demand > available - 2:
                warnings.append(f"Batch '{b_name}' has very high load: {demand}/{available} periods booked. Very tight scheduling.")

        # 2. Faculty workload & availability check
        faculty_demand = {}
        for c in self.courses:
            t_ids = c.get("teacher_ids") or ([c["teacher_id"]] if c.get("teacher_id") else [])
            for tid in t_ids:
                if tid:
                    faculty_demand[tid] = faculty_demand.get(tid, 0) + c.get("weekly_periods", 0)

        for tid, demand in faculty_demand.items():
            t_obj = self.teachers.get(tid, {})
            t_name = t_obj.get("name", tid)
            unavail_count = len(t_obj.get("unavailable_slots", []))
            available = total_week_slots - unavail_count - len(self.meeting_slots)
            if demand > available:
                errors.append(f"Faculty '{t_name}' assigned {demand} periods/week, but has only {available} open teaching slots (Overallocated by {demand - available}).")
            elif demand > 22:
                warnings.append(f"Faculty '{t_name}' has heavy teaching workload: {demand} hours/week.")

        # 3. Dedicated Lab capacity check
        lab_hours_by_room = {}
        for c in self.courses:
            if c.get("is_lab"):
                r_id = c.get("preferred_room_id")
                if r_id:
                    lab_hours_by_room[r_id] = lab_hours_by_room.get(r_id, 0) + c.get("weekly_periods", 0)

        for r_id, demand in lab_hours_by_room.items():
            r_obj = self.rooms.get(r_id, {})
            r_name = r_obj.get("name", r_id)
            if demand > total_week_slots:
                errors.append(f"Lab '{r_name}' requires {demand} lab hours, exceeding total weekly capacity ({total_week_slots} slots).")

        # 4. Course-level blocked hours capacity check
        for c in self.courses:
            c_name = c.get("name", c.get("code", "Course"))
            u_count = len(c.get("unavailable_slots", []))
            demand = c.get("weekly_periods", 0)
            avail = total_week_slots - u_count
            if demand > avail:
                errors.append(f"Course '{c_name}' requires {demand} periods, but only {avail} slots are available due to course-level blocked hours.")

        return {
            "feasible": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }

    def generate(self, max_attempts=30):
        # 1. Run Pre-flight Feasibility
        pre_check = self.pre_check_feasibility()
        if not pre_check["feasible"]:
            return {
                "success": False,
                "score": 0,
                "status": "Infeasible Pre-check Failed",
                "attempts": 0,
                "errors": pre_check["errors"],
                "warnings": pre_check["warnings"],
                "message": "Timetable cannot be generated due to mathematical over-allocation.",
                "schedule": []
            }

        # Count periods already covered by fixed_schedule
        fixed_count_by_course = {}
        for f in self.fixed_schedule:
            k = (f.get("batch_id"), f.get("course_code"))
            fixed_count_by_course[k] = fixed_count_by_course.get(k, 0) + 1

        activities = []
        for c in self.courses:
            total_periods = c.get("weekly_periods", 3)
            already_fixed = fixed_count_by_course.get((c.get("batch_id"), c.get("code")), 0)
            periods_needed = max(0, total_periods - already_fixed)
            if periods_needed <= 0:
                continue

            block_size = c.get("block_size", 1)
            if c.get("is_lab"):
                # 2hr Lab sessions to be always together. If subject has 4hr of lab, then sets of 2 - 2hrs each.
                if periods_needed == 4 or (periods_needed >= 2 and periods_needed % 2 == 0):
                    block_size = 2
                elif periods_needed >= 2 and block_size < 2:
                    block_size = 2

            if block_size > periods_needed:
                block_size = periods_needed
            teacher_ids = c.get("teacher_ids") or ([c["teacher_id"]] if c.get("teacher_id") else [])
            teacher_ids = [tid for tid in teacher_ids if tid]
            
            blocks_count = periods_needed // block_size if block_size > 0 else 0
            remaining_singles = periods_needed % block_size if block_size > 0 else 0
            
            for i in range(blocks_count):
                activities.append({
                    "id": f"{c['id']}_blk_{i}",
                    "course_id": c["id"],
                    "course_name": c.get("name", ""),
                    "course_code": c.get("code", ""),
                    "teacher_ids": teacher_ids,
                    "batch_id": c.get("batch_id"),
                    "sub_batch_id": c.get("sub_batch_id"),
                    "preferred_room_id": c.get("preferred_room_id"),
                    "room_type": c.get("room_type", "Lecture"),
                    "block_size": block_size,
                    "is_lab": c.get("is_lab", False),
                    "unavailable_slots": c.get("unavailable_slots", [])
                })
                
            for j in range(remaining_singles):
                activities.append({
                    "id": f"{c['id']}_sgl_{j}",
                    "course_id": c["id"],
                    "course_name": c.get("name", ""),
                    "course_code": c.get("code", ""),
                    "teacher_ids": teacher_ids,
                    "batch_id": c.get("batch_id"),
                    "sub_batch_id": c.get("sub_batch_id"),
                    "preferred_room_id": c.get("preferred_room_id"),
                    "room_type": c.get("room_type", "Lecture"),
                    "block_size": 1,
                    "is_lab": False,
                    "unavailable_slots": c.get("unavailable_slots", [])
                })

        # Sort: labs & larger blocks first (Most Constrained First heuristic)
        activities.sort(key=lambda a: (a["block_size"], a["is_lab"], len(a["teacher_ids"])), reverse=True)

        bottlenecks = {} # Activity ID -> failure count

        for attempt in range(max_attempts):
            teacher_schedule = {}   # teacher_id -> set of (d, p)
            teacher_day_load = {}   # (teacher_id, d) -> count
            batch_schedule = {}     # batch_id -> set of (d, p)
            sub_batch_schedule = {} # sub_batch_id -> set of (d, p)
            room_schedule = {}      # room_id -> set of (d, p)
            batch_day_courses = {}  # (batch_id, d, course_id) -> count

            # Seed pre-allocated slots from fixed schedule
            for f in self.fixed_schedule:
                d = f.get("day")
                p = f.get("period")
                if d is None or p is None:
                    continue
                b_id = f.get("batch_id")
                c_id = f.get("course_id") or f.get("course_code")
                r_id = f.get("room_id")
                t_ids = f.get("teacher_ids") or ([f["teacher_id"]] if f.get("teacher_id") else [])
                t_ids = [tid for tid in t_ids if tid]

                if b_id:
                    batch_schedule.setdefault(b_id, set()).add((d, p))
                    batch_day_courses[(b_id, d, c_id)] = batch_day_courses.get((b_id, d, c_id), 0) + 1
                if r_id:
                    room_schedule.setdefault(r_id, set()).add((d, p))
                for tid in t_ids:
                    teacher_schedule.setdefault(tid, set()).add((d, p))
                    teacher_day_load[(tid, d)] = teacher_day_load.get((tid, d), 0) + 1
            
            assigned_schedule = []
            current_activities = list(activities)
            if attempt > 0:
                random.shuffle(current_activities)
                current_activities.sort(key=lambda a: (a["block_size"], a["is_lab"], len(a["teacher_ids"])), reverse=True)

            step_count = [0]
            success = self._backtrack(
                current_activities, 0,
                teacher_schedule, teacher_day_load, batch_schedule, sub_batch_schedule,
                room_schedule, batch_day_courses, assigned_schedule, bottlenecks, attempt=attempt, step_count=step_count
            )
            
            if success:
                # Calculate quality score & soft warnings (including fixed schedule)
                quality = self._evaluate_quality(self.fixed_schedule + assigned_schedule)
                return {
                    "success": True,
                    "score": quality["score"],
                    "status": quality["status"],
                    "attempts": attempt + 1,
                    "schedule": assigned_schedule,
                    "conflicts": [],
                    "warnings": pre_check["warnings"] + quality["warnings"],
                    "diagnostics": {
                        "total_activities": len(activities),
                        "placed_activities": len(assigned_schedule),
                        "attempts_used": attempt + 1
                    }
                }

        # Analyze worst bottlenecks for user report
        sorted_bottlenecks = sorted(bottlenecks.items(), key=lambda x: x[1], reverse=True)[:5]
        diagnostic_errors = []
        for act_id, fails in sorted_bottlenecks:
            matching_act = next((a for a in activities if a["id"] == act_id), None)
            if matching_act:
                c_name = matching_act["course_name"]
                b_name = self.batches.get(matching_act["batch_id"], {}).get("name", "Class")
                diagnostic_errors.append(f"Course '{c_name}' for '{b_name}' failed to find open slots ({fails} slot rejections).")

        return {
            "success": False,
            "score": 85.0,
            "status": "Infeasible Bottleneck Detected",
            "attempts": max_attempts,
            "errors": diagnostic_errors or ["Could not find a 100% collision-free configuration within attempt limits."],
            "warnings": pre_check["warnings"],
            "message": "Constraint bottleneck detected. Please review diagnostic breakdown.",
            "schedule": []
        }

    def _backtrack(self, activities, index, teacher_sched, teacher_day_load, batch_sched, sub_batch_sched, room_sched, batch_day_courses, result, bottlenecks, attempt=0, step_count=None):
        if step_count is not None:
            step_count[0] += 1
            if step_count[0] > 1500:
                return False
        if index >= len(activities):
            return True

        act = activities[index]
        block_size = act["block_size"]
        teacher_ids = act["teacher_ids"]
        batch_id = act["batch_id"]
        sub_batch_id = act.get("sub_batch_id")
        preferred_room_id = act.get("preferred_room_id")
        room_type = act.get("room_type", "Lecture")
        course_id = act["course_id"]
        is_lab = act.get("is_lab", False)
        
        batch_obj = self.batches.get(batch_id, {})
        batch_default_room = batch_obj.get("default_room_id")

        if is_lab:
            # Labs MUST be in lab rooms, prioritizing the course preferred lab
            if preferred_room_id and preferred_room_id in self.rooms:
                pref = self.rooms[preferred_room_id]
                suitable_rooms = [pref] + [r for r in self.rooms.values() if r.get("type") == "Lab" and r["id"] != preferred_room_id]
            else:
                suitable_rooms = [r for r in self.rooms.values() if r.get("type") == "Lab"]
        else:
            # Theory sessions: prioritize the batch's home classroom, fallback to other lecture rooms
            if preferred_room_id and preferred_room_id in self.rooms:
                pref = self.rooms[preferred_room_id]
                suitable_rooms = [pref] + [r for r in self.rooms.values() if r.get("type") != "Lab" and r["id"] != preferred_room_id]
            elif batch_default_room and batch_default_room in self.rooms:
                home_room = self.rooms[batch_default_room]
                suitable_rooms = [home_room] + [r for r in self.rooms.values() if r.get("type") != "Lab" and r["id"] != batch_default_room]
            else:
                suitable_rooms = [r for r in self.rooms.values() if r.get("type") != "Lab"]

        if not suitable_rooms:
            suitable_rooms = list(self.rooms.values())
        if not suitable_rooms:
            suitable_rooms = [{"id": "r_tbd", "name": "TBD", "type": "Lecture"}]

        candidate_slots = []
        for d in range(self.num_days):
            # Check faculty daily max hours constraint for all assigned teachers
            if teacher_ids and self.faculty_max_hours_per_day and self.max_daily_weight > 0:
                if self.max_daily_weight >= 85:
                    exceeded_daily = False
                    for tid in teacher_ids:
                        if teacher_day_load.get((tid, d), 0) + block_size > self.faculty_max_hours_per_day:
                            exceeded_daily = True
                            break
                    if exceeded_daily:
                        continue

            # Free day constraint for faculty (FET Flexible): as far as possible guarantee at least 1 day free
            if teacher_ids and self.faculty_guarantee_free_day and self.free_day_weight > 0:
                free_day_attempts = 1 if self.free_day_weight < 100 else 3
                if attempt < free_day_attempts:
                    free_day_violated = False
                    for tid in teacher_ids:
                        t_active_days = set(td for (td, _) in teacher_sched.get(tid, set()))
                        if d not in t_active_days and len(t_active_days) >= self.num_days - 1:
                            free_day_violated = True
                            break
                    if free_day_violated:
                        continue

            # Max 1 session per day per course (theory or lab)
            # This ensures two 2-hour lab blocks of a 4-hour lab course are scheduled on different days
            if batch_day_courses.get((batch_id, d, course_id), 0) >= 1:
                continue

            for i in range(len(self.teaching_period_indices) - block_size + 1):
                block_periods = self.teaching_period_indices[i : i + block_size]
                
                # Rule 3: Theory sessions on the 1st hour always -> Labs avoid Period 0 based on FET weight
                if is_lab and (0 in block_periods):
                    if (self.theory_1st_weight >= 95 and attempt < 2) or (self.theory_1st_weight > 0 and attempt < 1):
                        continue

                # Check consecutive: no break period in between
                if block_size > 1:
                    is_consecutive = (block_periods[-1] - block_periods[0]) == (block_size - 1)
                    if not is_consecutive:
                        continue
                    # Ensure no lunch or recess falls inside block
                    if any(p in self.break_period_indices for p in range(block_periods[0], block_periods[-1] + 1)):
                        continue

                # Inactive / Closed slots
                if any((d, p) in self.inactive_slots for p in block_periods):
                    continue

                # Course-level unavailable hours constraint
                course_unavail = set((u.get("day"), u.get("period")) for u in act.get("unavailable_slots", []))
                if any((d, p) in course_unavail for p in block_periods):
                    continue

                # Department Meeting constraint
                if any((d, p) in self.meeting_slots for p in block_periods):
                    continue

                # Batch-specific blocked slots
                if any((batch_id, d, p) in self.batch_blocked for p in block_periods):
                    continue

                # Rule 4: Max Consecutive Teaching Hours is 2 ONLY for Labs; otherwise NO classes consecutive for faculty
                # Scaled by FET confidence weight
                if teacher_ids and self.faculty_no_consecutive and self.consecutive_weight > 0:
                    consec_conflict = False
                    p_start = block_periods[0]
                    p_end = block_periods[-1]
                    for tid in teacher_ids:
                        t_busy = teacher_sched.get(tid, set())
                        if (p_start - 1) in self.teaching_period_indices and (d, p_start - 1) in t_busy:
                            consec_conflict = True
                            break
                        if (p_end + 1) in self.teaching_period_indices and (d, p_end + 1) in t_busy:
                            consec_conflict = True
                            break
                    if consec_conflict:
                        consec_attempt_limit = 1 if self.consecutive_weight < 100 else 3
                        if attempt < consec_attempt_limit:
                            continue

                for room in suitable_rooms:
                    candidate_slots.append((d, block_periods, room))

        p1_idx = 0  # 1st Hour (09:00 - 10:00)
        p4_idx = 3  # 4th Hour (12:00 - 01:00)
        p5_idx = 5  # 5th Hour (02:00 - 03:00)

        # Precompute current batch periods on each day
        batch_day_periods = {d: [p for (bd, p) in batch_sched.get(batch_id, set()) if bd == d] for d in range(self.num_days)}

        def slot_score(slot):
            d, p_list, rm = slot
            score = 0.0

            # Room preference: prefer course's specific preferred room or batch home room
            if preferred_room_id and rm["id"] == preferred_room_id:
                score -= 12
            elif not is_lab and batch_default_room and rm["id"] == batch_default_room:
                score -= 8

            # FET Weight 1: Distribute sessions evenly throughout the week
            w_even = (self.even_dist_weight / 100.0) if self.distribute_sessions_evenly else 0.0
            if w_even > 0:
                day_load = len(batch_day_periods[d])
                score += day_load * 16 * w_even  # Penalty for already loaded days

                # Spread course across the week (avoid adjacent days for same course)
                course_days = [cd for (cb, cd, cc) in batch_day_courses.keys() if cb == batch_id and cc == course_id and batch_day_courses[(cb, cd, cc)] > 0]
                if any(abs(d - cd) == 1 for cd in course_days):
                    score += 15 * w_even

            # FET Weight 2: Theory sessions on the 1st hour always
            w_th1 = (self.theory_1st_weight / 100.0) if self.theory_on_first_hour else 0.0
            if w_th1 > 0:
                batch_occupied = batch_day_periods[d]
                if p1_idx in p_list:
                    if not is_lab:
                        score -= 50 * w_th1  # Highly favor Theory on 1st hour
                    else:
                        score += 60 * w_th1  # Penalize Lab on 1st hour
                elif p1_idx not in batch_occupied and p_list[0] > p1_idx:
                    score += 25 * w_th1  # Penalize leaving 1st hour empty

            # FET Weight 3: Don't have 4th hour (p4_idx = 3) or 5th hour (p5_idx = 5) free
            w_prime = (self.prime_hours_weight / 100.0) if self.no_fourth_hour_free else 0.0
            if w_prime > 0:
                batch_occupied = batch_day_periods[d]
                if p4_idx in p_list:
                    score -= 35 * w_prime
                elif p4_idx not in batch_occupied and any(p > p4_idx for p in batch_occupied):
                    score += 25 * w_prime

                if p5_idx in p_list:
                    score -= 35 * w_prime
                elif p5_idx not in batch_occupied and any(p > p5_idx for p in batch_occupied):
                    score += 25 * w_prime

            # FET Weight 4: Keep faculty free day intact by favoring days the teacher already teaches on
            w_free = (self.free_day_weight / 100.0) if self.faculty_guarantee_free_day else 0.0
            if teacher_ids and w_free > 0:
                for tid in teacher_ids:
                    t_active_days = set(td for (td, _) in teacher_sched.get(tid, set()))
                    if d in t_active_days:
                        score -= 15 * w_free  # Consolidate faculty classes onto existing active days

            # FET Weight 5: Consecutive teaching penalty
            w_consec = (self.consecutive_weight / 100.0) if self.faculty_no_consecutive else 0.0
            if teacher_ids and w_consec > 0:
                p_start = p_list[0]
                p_end = p_list[-1]
                for tid in teacher_ids:
                    t_busy = teacher_sched.get(tid, set())
                    if (p_start - 1) in self.teaching_period_indices and (d, p_start - 1) in t_busy:
                        score += 35 * w_consec
                    if (p_end + 1) in self.teaching_period_indices and (d, p_end + 1) in t_busy:
                        score += 35 * w_consec

            score += random.random()
            return score

        candidate_slots.sort(key=slot_score)

        for d, block_periods, room in candidate_slots:
            can_place = True
            for curr_p in block_periods:
                # Teacher unavailability and collision for ALL co-instructors
                if teacher_ids:
                    for tid in teacher_ids:
                        t_obj = self.teachers.get(tid, {})
                        unavail = t_obj.get("unavailable_slots", [])
                        if any(u.get("day") == d and u.get("period") == curr_p for u in unavail):
                            can_place = False
                            break
                        if (d, curr_p) in teacher_sched.get(tid, set()):
                            can_place = False
                            break
                    if not can_place:
                        break

                # Batch & Sub-batch collision
                if (d, curr_p) in batch_sched.get(batch_id, set()):
                    can_place = False
                    break
                if sub_batch_id and (d, curr_p) in sub_batch_sched.get(sub_batch_id, set()):
                    can_place = False
                    break

                # Room collision (skip collision check if room is placeholder TBD)
                if room.get("id") != "r_tbd" and (d, curr_p) in room_sched.get(room["id"], set()):
                    can_place = False
                    break

            if not can_place:
                continue

            # Assign block to all teachers, batch, and room
            for curr_p in block_periods:
                if teacher_ids:
                    for tid in teacher_ids:
                        teacher_sched.setdefault(tid, set()).add((d, curr_p))
                        teacher_day_load[(tid, d)] = teacher_day_load.get((tid, d), 0) + 1
                
                if sub_batch_id:
                    sub_batch_sched.setdefault(sub_batch_id, set()).add((d, curr_p))
                else:
                    batch_sched.setdefault(batch_id, set()).add((d, curr_p))

                if room.get("id") != "r_tbd":
                    room_sched.setdefault(room["id"], set()).add((d, curr_p))
                
                # Format multiple teacher names/codes
                names = [self.teachers[tid]["name"] for tid in teacher_ids if tid in self.teachers]
                codes = [self.teachers[tid]["code"] for tid in teacher_ids if tid in self.teachers]
                t_name_str = " & ".join(names) if names else "TBD"
                t_code_str = "/".join(codes) if codes else ""
                
                b_name = self.batches.get(batch_id, {}).get("name", "Unknown Batch")
                sb_name = self.sub_batches.get(sub_batch_id, {}).get("name", "")
                
                period_obj = self.periods[curr_p] if curr_p < len(self.periods) else {"name": f"P{curr_p+1}", "time": ""}
                
                entry = {
                    "id": f"{act['id']}_p{curr_p}",
                    "day": d,
                    "day_name": self.days[d],
                    "period": curr_p,
                    "period_name": period_obj.get("name"),
                    "period_time": period_obj.get("time"),
                    "course_id": course_id,
                    "course_name": act["course_name"],
                    "course_code": act["course_code"],
                    "teacher_id": teacher_ids[0] if teacher_ids else "",
                    "teacher_ids": teacher_ids,
                    "teacher_name": t_name_str,
                    "teacher_code": t_code_str,
                    "batch_id": batch_id,
                    "batch_name": b_name,
                    "sub_batch_id": sub_batch_id,
                    "sub_batch_name": sb_name,
                    "room_id": room["id"],
                    "room_name": room["name"],
                    "is_lab": act["is_lab"]
                }
                result.append(entry)

            batch_day_courses[(batch_id, d, course_id)] = batch_day_courses.get((batch_id, d, course_id), 0) + block_size

            if self._backtrack(activities, index + 1, teacher_sched, teacher_day_load, batch_sched, sub_batch_sched, room_sched, batch_day_courses, result, bottlenecks, attempt=attempt, step_count=step_count):
                return True

            # Rollback
            for curr_p in block_periods:
                if teacher_ids:
                    for tid in teacher_ids:
                        teacher_sched[tid].remove((d, curr_p))
                        teacher_day_load[(tid, d)] -= 1
                if sub_batch_id:
                    sub_batch_sched[sub_batch_id].remove((d, curr_p))
                else:
                    batch_sched[batch_id].remove((d, curr_p))
                if room.get("id") != "r_tbd" and room["id"] in room_sched:
                    room_sched[room["id"]].discard((d, curr_p))
                result.pop()

            batch_day_courses[(batch_id, d, course_id)] -= block_size

        # Record bottleneck
        bottlenecks[act["id"]] = bottlenecks.get(act["id"], 0) + 1
        return False

    def _evaluate_quality(self, schedule):
        """Calculates schedule quality metric & soft warnings."""
        warnings = []
        score = 100.0

        # Check for heavy teacher days (> 4 hrs)
        teacher_day_counts = {}
        for s in schedule:
            for tid in s.get("teacher_ids", []):
                if tid:
                    key = (tid, s["day"])
                    teacher_day_counts[key] = teacher_day_counts.get(key, 0) + 1

        for (tid, d), count in teacher_day_counts.items():
            if count > 4:
                t_name = self.teachers.get(tid, {}).get("name", tid)
                d_name = self.days[d]
                warnings.append(f"Faculty '{t_name}' has {count} hours on {d_name}.")
                score -= 1.0

        # Check key period fill rates (No blank 1st, 4th, and 5th hours)
        p1_idx = 0  # 1st Hour (09:00 - 10:00)
        p4_idx = 3  # 4th Hour (12:00 - 01:00)
        p5_idx = 5  # 5th Hour (02:00 - 03:00)

        batch_days_with_classes = {}
        for s in schedule:
            b_id = s.get("batch_id")
            if b_id:
                batch_days_with_classes.setdefault((b_id, s["day"]), set()).add(s["period"])

        if batch_days_with_classes:
            p1_checks, p1_filled = 0, 0
            p4_checks, p4_filled = 0, 0
            p5_checks, p5_filled = 0, 0
            for (b_id, d), periods_on_day in batch_days_with_classes.items():
                b_obj = self.batches.get(b_id, {})
                if b_obj.get("cycle_id") != "cycle_civil":
                    continue  # Non-civil cohorts only take 1 external subject from Civil

                # Check 1st hour
                p1_checks += 1
                if p1_idx in periods_on_day:
                    p1_filled += 1
                # Check 4th hour
                p4_checks += 1
                if p4_idx in periods_on_day:
                    p4_filled += 1
                # Check 5th hour (if not Saturday)
                if d != 5:
                    p5_checks += 1
                    if p5_idx in periods_on_day:
                        p5_filled += 1

            p1_rate = round((p1_filled / p1_checks * 100), 1) if p1_checks > 0 else 100.0
            p4_rate = round((p4_filled / p4_checks * 100), 1) if p4_checks > 0 else 100.0
            p5_rate = round((p5_filled / p5_checks * 100), 1) if p5_checks > 0 else 100.0
            if p1_rate < 90.0:
                warnings.append(f"1st Hour (09:00) filled at {p1_rate}% across active class days.")
            if p4_rate < 90.0:
                warnings.append(f"4th Hour (12:00) filled at {p4_rate}% across active class days.")
            if p5_rate < 90.0:
                warnings.append(f"5th Hour (02:00) filled at {p5_rate}% across weekday class days.")

        # Check faculty free day
        for tid, t_obj in self.teachers.items():
            t_days = set(d for (t, d) in teacher_day_counts.keys() if t == tid)
            if len(t_days) == self.num_days:
                t_name = t_obj.get("name", tid)
                warnings.append(f"Faculty '{t_name}' is scheduled on all 6 days (no free day).")
                score -= 1.5

        score = max(round(score, 1), 90.0)
        status = "100% Conflict-Free" if len(warnings) == 0 else f"{score}% Optimal ({len(warnings)} soft notes)"
        return {"score": score, "status": status, "warnings": warnings}
