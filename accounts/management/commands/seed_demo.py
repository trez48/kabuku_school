"""
Management command: python manage.py seed_demo

Creates sample students, enrollments, marks, attendance, fees, and events
so the admin dashboard charts and student dashboards are populated for demo.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
import random


class Command(BaseCommand):
    help = 'Seed demo data: students, marks, attendance, fees, events'

    def handle(self, *args, **options):
        from academics.models import Combination, ExamResult
        from academics.models import Event
        from teacher.models import (
            ClassRoom, Subject, StudentEnrollment,
            Mark, Attendance, FeeRecord, Timetable
        )
        from accounts.models import UserProfile
        from news.models import NewsPost
        from core.models import Staff

        self.stdout.write('Seeding demo data...')

        # ── Combinations ──────────────────────────────────────────────────
        pgm, _ = Combination.objects.get_or_create(
            code='PGM', defaults={'name': 'Physics, Geography, Mathematics', 'subjects': 'Physics,Geography,Mathematics'}
        )
        pcm, _ = Combination.objects.get_or_create(
            code='PCM', defaults={'name': 'Physics, Chemistry, Mathematics', 'subjects': 'Physics,Chemistry,Mathematics'}
        )

        # ── Subjects ──────────────────────────────────────────────────────
        subj_data = [
            ('PHY', 'Physics',     pgm), ('GEO', 'Geography',   pgm),
            ('MAT', 'Mathematics', pgm), ('CHE', 'Chemistry',    pcm),
            ('BIO', 'Biology',     pcm), ('ENG', 'English',      pgm),
        ]
        subjects = {}
        for code, name, combo in subj_data:
            s, _ = Subject.objects.get_or_create(code=code, defaults={'name': name, 'combination': combo})
            subjects[code] = s

        # ── Classrooms ────────────────────────────────────────────────────
        cls_pgm, _ = ClassRoom.objects.get_or_create(
            name='Form 5 PGM', defaults={'combination': pgm, 'year': 2026}
        )
        cls_pcm, _ = ClassRoom.objects.get_or_create(
            name='Form 5 PCM', defaults={'combination': pcm, 'year': 2026}
        )

        # ── Students ──────────────────────────────────────────────────────
        students_info = [
            ('john', 'John',    'Mwenda',   'S001', cls_pgm),
            ('grace','Grace',   'Kimaro',   'S002', cls_pgm),
            ('peter','Peter',   'Shayo',    'S003', cls_pgm),
            ('anna', 'Anna',    'Lema',     'S004', cls_pcm),
            ('david','David',   'Mramba',   'S005', cls_pcm),
            ('mary', 'Mary',    'Njau',     'S006', cls_pcm),
            ('james','James',   'Kileo',    'S007', cls_pgm),
            ('lucy', 'Lucy',    'Massawe',  'S008', cls_pcm),
        ]

        users = []
        for username, first, last, adm, classroom in students_info:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={'first_name': first, 'last_name': last,
                          'email': f'{username}@kabuku.ac.tz'}
            )
            if created:
                user.set_password('Student@2026')
                user.save()

            profile, _ = UserProfile.objects.get_or_create(
                user=user,
                defaults={'role': 'student', 'admission_number': adm,
                          'must_change_password': False}
            )

            StudentEnrollment.objects.get_or_create(
                student=user, defaults={'classroom': classroom}
            )
            users.append((user, classroom))

        self.stdout.write(f'  Created {len(users)} students')

        # ── Marks ─────────────────────────────────────────────────────────
        exam_types = ['ca', 'midterm', 'terminal', 'mock']
        terms = ['Term 1', 'Term 2']
        mark_count = 0
        # get or create a teacher user to use as entered_by
        teacher_user, _ = User.objects.get_or_create(
            username='teacher_demo',
            defaults={'first_name': 'Demo', 'last_name': 'Teacher',
                      'email': 'teacher@kabuku.ac.tz'}
        )
        for user, classroom in users:
            combo_subjects = [s for s in subjects.values()
                              if s.combination == classroom.combination]
            for subj in combo_subjects:
                for term in terms:
                    exam_type = random.choice(exam_types)
                    score = random.randint(30, 98)
                    Mark.objects.get_or_create(
                        student=user, subject=subj,
                        exam_type=exam_type, term=term, year=2026,
                        defaults={
                            'score': score,
                            'max_score': 100,
                            'classroom': classroom,
                            'entered_by': teacher_user,
                        }
                    )
                    mark_count += 1

        self.stdout.write(f'  Created {mark_count} marks')

        # ── Attendance ────────────────────────────────────────────────────
        from datetime import date, timedelta
        att_count = 0
        statuses = ['present', 'present', 'present', 'present', 'absent', 'late']
        today = date.today()
        for user, classroom in users:
            for days_ago in range(1, 31):
                d = today - timedelta(days=days_ago)
                if d.weekday() < 5:  # Mon–Fri only
                    Attendance.objects.get_or_create(
                        student=user, classroom=classroom, date=d,
                        defaults={'status': random.choice(statuses)}
                    )
                    att_count += 1

        self.stdout.write(f'  Created {att_count} attendance records')

        # ── Fees ──────────────────────────────────────────────────────────
        fee_count = 0
        for user, classroom in users:
            amount = random.choice([250000, 300000, 350000])
            paid = random.randint(0, amount)
            FeeRecord.objects.get_or_create(
                student=user,
                description='School Fees 2026',
                defaults={
                    'amount': amount,
                    'paid': paid,
                    'due_date': date(2026, 12, 31),
                }
            )
            fee_count += 1

        self.stdout.write(f'  Created {fee_count} fee records')

        # ── Events ────────────────────────────────────────────────────────
        events_data = [
            ('End of Term Exams',       date(2026, 10, 15), 'School Hall'),
            ('Prize Giving Day',        date(2026, 11, 5),  'School Ground'),
            ('School Sports Day',       date(2026, 10, 25), 'Sports Field'),
            ('Parents Meeting',         date(2026, 10, 10), 'School Hall'),
            ('National Exams (NECTA)',  date(2026, 11, 20), 'Various Centers'),
        ]
        for title, event_date, location in events_data:
            Event.objects.get_or_create(
                title=title,
                defaults={'date': event_date, 'location': location, 'description': title}
            )

        self.stdout.write('  Created events')

        # ── News ──────────────────────────────────────────────────────────
        news_data = [
            ('School Opens for Term 3',
             'All students are expected to report by 7th October 2026.'),
            ('NECTA Registration Deadline',
             'Form 6 students must complete NECTA registration by 15th October.'),
            ('New Science Laboratory Opened',
             'The school has opened a new fully equipped science laboratory.'),
        ]
        for title, content in news_data:
            NewsPost.objects.get_or_create(
                title=title,
                defaults={'content': content, 'published': True}
            )

        self.stdout.write('  Created news posts')

        # ── Staff (core model for display) ───────────────────────────────
        staff_data = [
            ('Mr. Joseph Mrema',   'headmaster', 'Mathematics', 15),
            ('Ms. Fatuma Moshi',   'teacher',    'Physics',      8),
            ('Mr. Emmanuel Kileo', 'teacher',    'Chemistry',    6),
            ('Ms. Grace Shayo',    'teacher',    'Geography',    5),
        ]
        for name, role, subject, exp in staff_data:
            Staff.objects.get_or_create(
                name=name,
                defaults={'role': role, 'subject': subject,
                          'experience': exp, 'qualification': 'B.Ed'}
            )
        self.stdout.write('  Created staff profiles')

        # ── Teacher login accounts ────────────────────────────────────────
        teacher_accounts = [
            ('teacher1', 'Fatuma',   'Moshi',  'teacher1@kabuku.ac.tz', cls_pgm),
            ('teacher2', 'Emmanuel', 'Kileo',  'teacher2@kabuku.ac.tz', cls_pcm),
        ]
        for username, first, last, email, classroom in teacher_accounts:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={'first_name': first, 'last_name': last, 'email': email}
            )
            if created:
                user.set_password('Teacher@2026')
                user.save()
            UserProfile.objects.get_or_create(
                user=user,
                defaults={'role': 'teacher', 'must_change_password': False}
            )
        self.stdout.write('  Created 2 teacher accounts')

        # ── Parent login accounts ─────────────────────────────────────────
        parent_child_map = [
            ('parent1', 'Agnes',   'Mwenda', 'parent1@gmail.com', 'john'),
            ('parent2', 'Charles', 'Kimaro', 'parent2@gmail.com', 'grace'),
            ('parent3', 'Helena',  'Lema',   'parent3@gmail.com', 'anna'),
        ]
        for p_username, first, last, email, child_username in parent_child_map:
            child_user = User.objects.filter(username=child_username).first()
            if not child_user:
                continue
            child_profile = UserProfile.objects.filter(user=child_user).first()
            if not child_profile:
                continue
            p_user, created = User.objects.get_or_create(
                username=p_username,
                defaults={'first_name': first, 'last_name': last, 'email': email}
            )
            if created:
                p_user.set_password('Parent@2026')
                p_user.save()
            UserProfile.objects.get_or_create(
                user=p_user,
                defaults={
                    'role': 'parent',
                    'parent_of': child_profile,
                    'must_change_password': False,
                }
            )
        self.stdout.write('  Created 3 parent accounts')

        self.stdout.write(self.style.SUCCESS(
            '\n✅ Demo data seeded successfully!\n\n'
            '   STUDENTS (8)\n'
            '   Usernames: john, grace, peter, anna, david, mary, james, lucy\n'
            '   Password:  Student@2026\n\n'
            '   TEACHERS (2)\n'
            '   Usernames: teacher1, teacher2\n'
            '   Password:  Teacher@2026\n\n'
            '   PARENTS (3)\n'
            '   Usernames: parent1 (child=john), parent2 (child=grace), parent3 (child=anna)\n'
            '   Password:  Parent@2026\n\n'
            '   ADMIN: create with python manage.py createsuperuser\n'
        ))
