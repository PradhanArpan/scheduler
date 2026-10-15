import json, sys
from scheduler import TimetableScheduler

with open('timetable_data.json', encoding='utf-8') as f:
    data = json.load(f)

courses = [s for s in data['unmapped_subjects'] if s.get('semester_type') == 'Even']
s = TimetableScheduler(
    data['config'],
    data['faculty'],
    data['rooms'],
    data['batches'],
    courses,
    sub_batches=data.get('sub_batches', []),
    fixed_schedule=data.get('fixed_ce234p_schedule', [])
)

res = s.generate(max_attempts=30)
print('Generate success:', res['success'], flush=True)
print('Score:', res.get('score'), flush=True)
print('Status:', res.get('status'), flush=True)
print('Placed dynamic slots:', len(res.get('schedule', [])), flush=True)
total_all = len(res.get('schedule', [])) + len(data.get('fixed_ce234p_schedule', []))
print('Combined Total Timetable Slots:', total_all, flush=True)

if res['success']:
    # Save into timetable
    combined = list(data.get('fixed_ce234p_schedule', [])) + res['schedule']
    data['timetable'] = combined
    with open('timetable_data.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    print("Timetable generated and saved successfully!", flush=True)
else:
    print('Errors:', res.get('errors'), flush=True)
    print('Warnings:', res.get('warnings'), flush=True)
