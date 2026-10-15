import json
import os

data_path = os.path.join(os.path.dirname(__file__), 'timetable_data.json')
with open(data_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

# 1. Map batch names to IDs
batch_map = {b['name']: b['id'] for b in data['batches']}

# 2. Update fixed_ce234p_schedule with batch_id and course_name
for item in data.get('fixed_ce234p_schedule', []):
    b_name = item.get('batch_name')
    if b_name in batch_map:
        item['batch_id'] = batch_map[b_name]
    if item.get('is_lab'):
        item['course_code'] = 'CE 234P-LAB'
        item['course_name'] = 'Basics of Civil Engineering and Engineering Mechanics (Practical)'
    else:
        item['course_code'] = 'CE 234P'
        item['course_name'] = 'Basics of Civil Engineering and Engineering Mechanics (Theory)'

# 3. Add 1st year subjects to unmapped_subjects for both semesters
batches_1st = [b for b in data['batches'] if b.get('cycle_id') in ['cycle_phy', 'cycle_che']]
existing_ids = set(s['id'] for s in data['unmapped_subjects'])

added_count = 0
new_subjects = []

for sem in ['Even', 'Odd']:
    for b in batches_1st:
        b_id = b['id']
        b_name = b['name']
        
        # Theory
        th_id = f's_{sem.lower()}_ce234p_th_{b_id}'
        if th_id not in existing_ids:
            new_subjects.append({
                'id': th_id,
                'code': 'CE 234P',
                'name': 'Basics of Civil Engineering and Engineering Mechanics (Theory)',
                'semester_type': sem,
                'batch_id': b_id,
                'weekly_periods': 4,
                'is_lab': False,
                'block_size': 1,
                'room_type': 'Lecture',
                'teacher_id': '',
                'teacher_ids': []
            })
            existing_ids.add(th_id)
            added_count += 1
            
        # Practical
        lab_id = f's_{sem.lower()}_ce234p_lab_{b_id}'
        if lab_id not in existing_ids:
            new_subjects.append({
                'id': lab_id,
                'code': 'CE 234P-LAB',
                'name': 'Basics of Civil Engineering and Engineering Mechanics (Practical)',
                'semester_type': sem,
                'batch_id': b_id,
                'weekly_periods': 2,
                'is_lab': True,
                'block_size': 2,
                'room_type': 'Lab',
                'preferred_room_id': 'r_mt_lab',
                'teacher_id': '',
                'teacher_ids': []
            })
            existing_ids.add(lab_id)
            added_count += 1

data['unmapped_subjects'].extend(new_subjects)

with open(data_path, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2)

print(f"Added {added_count} subjects. Total subjects in unmapped_subjects: {len(data['unmapped_subjects'])}")
