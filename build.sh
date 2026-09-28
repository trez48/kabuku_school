#!/bin/bash
# Railway build script for kabuku_school
python manage.py collectstatic --noinput
python manage.py migrate --noinput
