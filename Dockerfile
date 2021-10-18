FROM python:3.7

ENV PYTHONUNBUFFERED=1

RUN mkdir /code
WORKDIR /code

RUN pip install --upgrade pip==20.2.4
RUN apt-get update 
RUN apt-get install -y netcat
COPY requirements.txt /code/
RUN pip install -r requirements.txt

EXPOSE 8000

COPY . /code/

#CMD ["gunicorn", "--bind", ":8000", "--workers", "8", "dds.wsgi:application"]
CMD python manage.py runserver 0.0.0.0:8000

COPY ./entrypoint.sh /
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
