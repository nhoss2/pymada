test:
	python manage.py test

setup-test-server: setup add-test-data run-server

setup:
	rm -f db.sqlite3
	python manage.py makemigrations
	python manage.py migrate

add-test-data:
	python add_test_data.py

run-server:
	python control.py

run-debug-server: setup add-test-data
	python manage.py runserver


.PHONY: setup setup-test-server add-test-data run-server run-debug-server test
