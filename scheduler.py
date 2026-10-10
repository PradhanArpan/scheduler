import random
from copy import deepcopy

class TimetableScheduler:
    def __init__(self, config, teachers, rooms, batches, courses):
        """
        config: {
            "days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
            "periods_per_day": 6,
            "recess_after_period": 3, # 1-indexed, recess after period 3 (before 4)
            "period_times": ["09:00 - 10:00", "10:00 - 11:00", "11:00 - 12:00", "01:00 - 02:00", "02:00 - 03:00", "03:00 - 04:00"]
        }
        """
        self.config = config
        self.days = config.get("days", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])
        self.num_days = len(self.days)
        self.periods_per_day = config.get("periods_per_day", 6)
        self.recess_after = config.get("recess_after_period", 3)
        
        self.teachers = {t["id"]: t for t in teachers}
        self.rooms = {r["id"]: r for r in rooms}
        self.batches = {b["id"]: b for b in batches}
        self.courses = courses

    def generate(self, max_attempts=50):
        """
        Attempts to generate a conflict-free schedule using backtracking with randomized heuristics.
        """
        # Create activities list
        activities = []
        for c in self.courses:
            periods_needed = c.get("weekly_periods", 3)
            block_size = c.get("block_size", 1) # e.g. 2 for 2-hour lab
            
            # Number of blocks
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
                    "preferred_room_id": c.get("preferred_room_id"),
                    "room_type": c.get("room_type", "Lecture"),
                    "block_size": 1,
                    "is_lab": False
                })

        # Sort activities: Larger blocks and lab activities first (hardest to place)
        activities.sort(key=lambda a: (a["block_size"], a["is_lab"]), reverse=True)

        for attempt in range(max_attempts):
            # Track occupied resources: (day, period) -> set of occupied IDs
            teacher_schedule = {} # teacher_id -> set of (d, p)
            batch_schedule = {}   # batch_id -> set of (d, p)
            room_schedule = {}    # room_id -> set of (d, p)
            batch_day_courses = {} # (batch_id, d, course_id) -> count of periods
            
            # Result list of assigned slots:
            # [{ day, period, course_id, course_name, course_code, teacher_id, teacher_name, batch_id, batch_name, room_id, room_name }]
            assigned_schedule = []
            
            # Shuffle order slightly across attempts while keeping large blocks first
            current_activities = list(activities)
            if attempt > 0:
                random.shuffle(current_activities)
                current_activities.sort(key=lambda a: (a["block_size"], a["is_lab"]), reverse=True)

            success = self._backtrack(
                current_activities, 0,
                teacher_schedule, batch_schedule, room_schedule, batch_day_courses,
                assigned_schedule
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
            "message": "Could not find a 100% conflict-free schedule. Try relaxing teacher unavailability or adding more rooms/time slots.",
            "schedule": []
        }

    def _backtrack(self, activities, index, teacher_sched, batch_sched, room_sched, batch_day_courses, result):
        if index >= len(activities):
            return True

        act = activities[index]
        block_size = act["block_size"]
        teacher_id = act["teacher_id"]
        batch_id = act["batch_id"]
        preferred_room_id = act.get("preferred_room_id")
        room_type = act.get("room_type", "Lecture")
        course_id = act["course_id"]
        
        # Suitable rooms
        suitable_rooms = [
            r for r in self.rooms.values()
            if r.get("type", "Lecture") == room_type or (room_type == "Lecture" and r.get("type") != "Lab")
        ]
        if preferred_room_id and preferred_room_id in self.rooms:
            # Put preferred room first
            pref = self.rooms[preferred_room_id]
            suitable_rooms = [pref] + [r for r in suitable_rooms if r["id"] != preferred_room_id]
        elif not suitable_rooms:
            suitable_rooms = list(self.rooms.values())

        # Generate candidate starting slots: (day_idx, start_period_idx, room)
        candidate_slots = []
        for d in range(self.num_days):
            for p in range(self.periods_per_day - block_size + 1):
                # Don't span across recess break if block_size > 1
                if block_size > 1 and self.recess_after > 0:
                    if p < self.recess_after and (p + block_size) > self.recess_after:
                        continue # spans across lunch recess!

                for room in suitable_rooms:
                    candidate_slots.append((d, p, room))

        # Heuristic scoring to pick optimal slots first (spread across days, avoid teacher overload)
        def slot_score(slot):
            d, p, rm = slot
            # Penalize if batch already has this course today
            day_count = batch_day_courses.get((batch_id, d, course_id), 0)
            score = day_count * 10
            # Prefer preferred room
            if preferred_room_id and rm["id"] == preferred_room_id:
                score -= 5
            # Small random tie-breaker
            score += random.random()
            return score

        candidate_slots.sort(key=slot_score)

        for d, p, room in candidate_slots:
            # Check availability for all periods in the block
            can_place = True
            for offset in range(block_size):
                curr_p = p + offset
                
                # Check teacher unavailability (from teacher settings)
                t_obj = self.teachers.get(teacher_id, {})
                unavail = t_obj.get("unavailable_slots", []) # e.g. [{"day": 0, "period": 1}]
                if any(u.get("day") == d and u.get("period") == curr_p for u in unavail):
                    can_place = False
                    break

                # Check teacher collision
                if (d, curr_p) in teacher_sched.get(teacher_id, set()):
                    can_place = False
                    break

                # Check batch collision
                if (d, curr_p) in batch_sched.get(batch_id, set()):
                    can_place = False
                    break

                # Check room collision
                if (d, curr_p) in room_sched.get(room["id"], set()):
                    can_place = False
                    break

            if not can_place:
                continue

            # Place the activity block
            assigned_entries = []
            for offset in range(block_size):
                curr_p = p + offset
                teacher_sched.setdefault(teacher_id, set()).add((d, curr_p))
                batch_sched.setdefault(batch_id, set()).add((d, curr_p))
                room_sched.setdefault(room["id"], set()).add((d, curr_p))
                
                t_name = self.teachers.get(teacher_id, {}).get("name", "Unknown Teacher")
                t_code = self.teachers.get(teacher_id, {}).get("code", "")
                b_name = self.batches.get(batch_id, {}).get("name", "Unknown Batch")
                
                entry = {
                    "id": f"{act['id']}_p{offset}",
                    "day": d,
                    "day_name": self.days[d],
                    "period": curr_p,
                    "period_time": self.config.get("period_times", [])[curr_p] if curr_p < len(self.config.get("period_times", [])) else f"Period {curr_p+1}",
                    "course_id": course_id,
                    "course_name": act["course_name"],
                    "course_code": act["course_code"],
                    "teacher_id": teacher_id,
                    "teacher_name": t_name,
                    "teacher_code": t_code,
                    "batch_id": batch_id,
                    "batch_name": b_name,
                    "room_id": room["id"],
                    "room_name": room["name"],
                    "is_lab": act["is_lab"]
                }
                assigned_entries.append(entry)
                result.append(entry)

            batch_day_courses[(batch_id, d, course_id)] = batch_day_courses.get((batch_id, d, course_id), 0) + block_size

            # Recurse
            if self._backtrack(activities, index + 1, teacher_sched, batch_sched, room_sched, batch_day_courses, result):
                return True

            # Undo placement
            for offset in range(block_size):
                curr_p = p + offset
                teacher_sched[teacher_id].remove((d, curr_p))
                batch_sched[batch_id].remove((d, curr_p))
                room_sched[room["id"]].remove((d, curr_p))
                result.pop()

            batch_day_courses[(batch_id, d, course_id)] -= block_size

        return False
