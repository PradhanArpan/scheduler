import random
from copy import deepcopy

class TimetableScheduler:
    def __init__(self, config, teachers, rooms, batches, courses, sub_batches=None):
        """
        config: {
            "days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
            "periods": [
                {"id": "p1", "name": "Period 1", "time": "09:00 - 10:00", "is_break": False},
                {"id": "p2", "name": "Period 2", "time": "10:00 - 11:00", "is_break": False},
                {"id": "p3", "name": "Period 3", "time": "11:00 - 12:00", "is_break": False},
                {"id": "p4", "name": "Period 4", "time": "12:00 - 01:00", "is_break": False},
                {"id": "lunch", "name": "Lunch Break", "time": "01:00 - 02:00", "is_break": True},
                {"id": "p5", "name": "Period 5", "time": "02:00 - 03:00", "is_break": False},
                {"id": "p6", "name": "Period 6", "time": "03:00 - 04:00", "is_break": False}
            ],
            "day_working_matrix": {
                # day_index -> set of active period_indices
            }
        }
        """
        self.config = config
        self.days = config.get("days", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"])
        self.num_days = len(self.days)
        
        # Support both new rich periods array and legacy period_times
        if "periods" in config:
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
        
        # Active teaching slot indices (excluding breaks)
        self.teaching_period_indices = [i for i, p in enumerate(self.periods) if not p.get("is_break", False)]
        
        # Day inactive slots (e.g. Saturday afternoon)
        self.inactive_slots = set()
        saturday_idx = 5 if self.num_days >= 6 else -1
        sat_max = config.get("saturday_max_period", 4)
        if saturday_idx >= 0 and sat_max is not None:
            # find the index in periods for the sat_max teaching period
            teaching_seen = 0
            for idx, p in enumerate(self.periods):
                if not p.get("is_break"):
                    teaching_seen += 1
                    if teaching_seen > sat_max:
                        self.inactive_slots.add((saturday_idx, idx))
                else:
                    if teaching_seen >= sat_max:
                        self.inactive_slots.add((saturday_idx, idx))

        # Explicit custom inactive matrix from config if set
        if "day_working_matrix" in config:
            # format: {"0": [True, True, ...]}
            for d_str, slot_flags in config["day_working_matrix"].items():
                d = int(d_str)
                for p_idx, is_active in enumerate(slot_flags):
                    if not is_active:
                        self.inactive_slots.add((d, p_idx))

        self.teachers = {t["id"]: t for t in teachers}
        self.rooms = {r["id"]: r for r in rooms}
        self.batches = {b["id"]: b for b in batches}
        self.sub_batches = {sb["id"]: sb for sb in (sub_batches or [])}
        self.courses = courses

    def generate(self, max_attempts=100):
        activities = []
        for c in self.courses:
            periods_needed = c.get("weekly_periods", 3)
            block_size = c.get("block_size", 1)
            
            blocks_count = periods_needed // block_size
            remaining_singles = periods_needed % block_size
            
            for i in range(blocks_count):
                activities.append({
                    "id": f"{c['id']}_blk_{i}",
                    "course_id": c["id"],
                    "course_name": c.get("name", ""),
                    "course_code": c.get("code", ""),
                    "teacher_id": c.get("teacher_id"),
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
                    "teacher_id": c.get("teacher_id"),
                    "batch_id": c.get("batch_id"),
                    "sub_batch_id": c.get("sub_batch_id"),
                    "preferred_room_id": c.get("preferred_room_id"),
                    "room_type": c.get("room_type", "Lecture"),
                    "block_size": 1,
                    "is_lab": False
                })

        activities.sort(key=lambda a: (a["block_size"], a["is_lab"]), reverse=True)

        for attempt in range(max_attempts):
            teacher_schedule = {} # teacher_id -> set of (d, p)
            batch_schedule = {}   # batch_id -> set of (d, p)
            sub_batch_schedule = {} # sub_batch_id -> set of (d, p)
            room_schedule = {}    # room_id -> set of (d, p)
            batch_day_courses = {} # (batch_id, d, course_id) -> count
            
            assigned_schedule = []
            current_activities = list(activities)
            if attempt > 0:
                random.shuffle(current_activities)
                current_activities.sort(key=lambda a: (a["block_size"], a["is_lab"]), reverse=True)

            success = self._backtrack(
                current_activities, 0,
                teacher_schedule, batch_schedule, sub_batch_schedule,
                room_schedule, batch_day_courses, assigned_schedule
            )
            
            if success:
                return {
                    "success": True,
                    "attempts": attempt + 1,
                    "schedule": assigned_schedule,
                    "conflicts": []
                }

        return {
            "success": False,
            "attempts": max_attempts,
            "message": "Could not find a 100% conflict-free schedule with current constraints.",
            "schedule": []
        }

    def _backtrack(self, activities, index, teacher_sched, batch_sched, sub_batch_sched, room_sched, batch_day_courses, result):
        if index >= len(activities):
            return True

        act = activities[index]
        block_size = act["block_size"]
        teacher_id = act["teacher_id"]
        batch_id = act["batch_id"]
        sub_batch_id = act.get("sub_batch_id")
        preferred_room_id = act.get("preferred_room_id")
        room_type = act.get("room_type", "Lecture")
        course_id = act["course_id"]
        
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
            # Iterate through teaching periods
            for i in range(len(self.teaching_period_indices) - block_size + 1):
                block_periods = self.teaching_period_indices[i : i + block_size]
                
                # Check consecutive: ensure no breaks fall inside the block!
                if block_size > 1:
                    is_consecutive = (block_periods[-1] - block_periods[0]) == (block_size - 1)
                    if not is_consecutive:
                        continue # contains a break in between!

                # Check if any slot in block is inactive on this day (e.g. Sat afternoon)
                if any((d, p) in self.inactive_slots for p in block_periods):
                    continue

                for room in suitable_rooms:
                    candidate_slots.append((d, block_periods, room))

        def slot_score(slot):
            d, p_list, rm = slot
            day_count = batch_day_courses.get((batch_id, d, course_id), 0)
            score = day_count * 15
            if preferred_room_id and rm["id"] == preferred_room_id:
                score -= 6
            score += random.random()
            return score

        candidate_slots.sort(key=slot_score)

        for d, block_periods, room in candidate_slots:
            can_place = True
            for curr_p in block_periods:
                # Teacher unavailability
                if teacher_id:
                    t_obj = self.teachers.get(teacher_id, {})
                    unavail = t_obj.get("unavailable_slots", [])
                    if any(u.get("day") == d and u.get("period") == curr_p for u in unavail):
                        can_place = False
                        break
                    if (d, curr_p) in teacher_sched.get(teacher_id, set()):
                        can_place = False
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

            # Assign block
            for curr_p in block_periods:
                if teacher_id:
                    teacher_sched.setdefault(teacher_id, set()).add((d, curr_p))
                
                # If sub-batch assigned, mark sub-batch and optionally batch
                if sub_batch_id:
                    sub_batch_sched.setdefault(sub_batch_id, set()).add((d, curr_p))
                else:
                    batch_sched.setdefault(batch_id, set()).add((d, curr_p))

                room_sched.setdefault(room["id"], set()).add((d, curr_p))
                
                t_obj = self.teachers.get(teacher_id, {})
                t_name = t_obj.get("name", "TBD")
                t_code = t_obj.get("code", "")
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
                    "teacher_id": teacher_id,
                    "teacher_name": t_name,
                    "teacher_code": t_code,
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

            if self._backtrack(activities, index + 1, teacher_sched, batch_sched, sub_batch_sched, room_sched, batch_day_courses, result):
                return True

            # Rollback
            for curr_p in block_periods:
                if teacher_id:
                    teacher_sched[teacher_id].remove((d, curr_p))
                if sub_batch_id:
                    sub_batch_sched[sub_batch_id].remove((d, curr_p))
                else:
                    batch_sched[batch_id].remove((d, curr_p))
                room_sched[room["id"]].remove((d, curr_p))
                result.pop()

            batch_day_courses[(batch_id, d, course_id)] -= block_size

        return False
