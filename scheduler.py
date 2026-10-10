import random
from copy import deepcopy

class TimetableScheduler:
    def __init__(self, config, teachers, rooms, batches, courses, sub_batches=None):
        self.config = config
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

        # Advanced constraints configuration
        adv = config.get("advanced_constraints", {})
        self.faculty_max_hours_per_day = adv.get("faculty_max_hours_per_day", 4)
        self.faculty_no_consecutive_theory = adv.get("faculty_no_consecutive_theory", False)
        self.faculty_max_consecutive_hours = adv.get("faculty_max_consecutive_hours", 3)
        self.single_theory_per_day_per_course = adv.get("single_theory_per_day_per_course", True)
        
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
        self.batches = {b["id"]: b for b in batches}
        self.sub_batches = {sb["id"]: sb for sb in (sub_batches or [])}
        self.courses = courses

    def pre_check_feasibility(self):
        """
        FET-style pre-flight validation: Checks capacity, over-allocation,
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
            # count batch blocked slots
            blocked_count = sum(1 for (b, d, p) in self.batch_blocked if b == b_id)
            available = total_week_slots - blocked_count
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

        return {
            "feasible": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }

    def generate(self, max_attempts=200):
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

        activities = []
        for c in self.courses:
            periods_needed = c.get("weekly_periods", 3)
            block_size = c.get("block_size", 1)
            teacher_ids = c.get("teacher_ids") or ([c["teacher_id"]] if c.get("teacher_id") else [])
            
            blocks_count = periods_needed // block_size
            remaining_singles = periods_needed % block_size
            
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
                    "is_lab": c.get("is_lab", False)
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
                    "is_lab": False
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
            
            assigned_schedule = []
            current_activities = list(activities)
            if attempt > 0:
                random.shuffle(current_activities)
                current_activities.sort(key=lambda a: (a["block_size"], a["is_lab"], len(a["teacher_ids"])), reverse=True)

            success = self._backtrack(
                current_activities, 0,
                teacher_schedule, teacher_day_load, batch_schedule, sub_batch_schedule,
                room_schedule, batch_day_courses, assigned_schedule, bottlenecks
            )
            
            if success:
                # Calculate quality score & soft warnings
                quality = self._evaluate_quality(assigned_schedule)
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

    def _backtrack(self, activities, index, teacher_sched, teacher_day_load, batch_sched, sub_batch_sched, room_sched, batch_day_courses, result, bottlenecks):
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
        
        suitable_rooms = [
            r for r in self.rooms.values()
            if r.get("type", "Lecture") == room_type or (room_type == "Lecture" and r.get("type") != "Lab")
        ]
        if preferred_room_id and preferred_room_id in self.rooms:
            pref = self.rooms[preferred_room_id]
            suitable_rooms = [pref] + [r for r in suitable_rooms if r["id"] != preferred_room_id]
        elif not suitable_rooms:
            suitable_rooms = list(self.rooms.values())

        candidate_slots = []
        for d in range(self.num_days):
            # Check faculty daily max hours constraint for all assigned teachers
            if teacher_ids and self.faculty_max_hours_per_day:
                exceeded_daily = False
                for tid in teacher_ids:
                    if teacher_day_load.get((tid, d), 0) + block_size > self.faculty_max_hours_per_day:
                        exceeded_daily = True
                        break
                if exceeded_daily:
                    continue

            # Check single theory lecture per day per subject
            if not is_lab and self.single_theory_per_day_per_course:
                if batch_day_courses.get((batch_id, d, course_id), 0) >= 1:
                    continue

            for i in range(len(self.teaching_period_indices) - block_size + 1):
                block_periods = self.teaching_period_indices[i : i + block_size]
                
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

                # Department Meeting constraint
                if any((d, p) in self.meeting_slots for p in block_periods):
                    continue

                # Batch-specific blocked slots
                if any((batch_id, d, p) in self.batch_blocked for p in block_periods):
                    continue

                # Faculty no-consecutive-theory constraint
                if teacher_ids and not is_lab and self.faculty_no_consecutive_theory:
                    consec_conflict = False
                    first_p = block_periods[0]
                    last_p = block_periods[-1]
                    for tid in teacher_ids:
                        t_busy = teacher_sched.get(tid, set())
                        if (d, first_p - 1) in t_busy or (d, last_p + 1) in t_busy:
                            consec_conflict = True
                            break
                    if consec_conflict:
                        continue

                for room in suitable_rooms:
                    candidate_slots.append((d, block_periods, room))

        # Heuristic sorting: favor preferred rooms and uniform day spread
        def slot_score(slot):
            d, p_list, rm = slot
            day_count = batch_day_courses.get((batch_id, d, course_id), 0)
            score = day_count * 20
            if preferred_room_id and rm["id"] == preferred_room_id:
                score -= 8
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

                # Room collision
                if (d, curr_p) in room_sched.get(room["id"], set()):
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

            if self._backtrack(activities, index + 1, teacher_sched, teacher_day_load, batch_sched, sub_batch_sched, room_sched, batch_day_courses, result, bottlenecks):
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
                room_sched[room["id"]].remove((d, curr_p))
                result.pop()

            batch_day_courses[(batch_id, d, course_id)] -= block_size

        # Record bottleneck
        bottlenecks[act["id"]] = bottlenecks.get(act["id"], 0) + 1
        return False

    def _evaluate_quality(self, schedule):
        """Calculates FET-style quality metric & soft warnings."""
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

        score = max(round(score, 1), 90.0)
        status = "100% Conflict-Free" if len(warnings) == 0 else f"{score}% Optimal ({len(warnings)} soft notes)"
        return {"score": score, "status": status, "warnings": warnings}
