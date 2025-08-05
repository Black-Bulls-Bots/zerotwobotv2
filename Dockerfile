FROM jokerhacker/zerotwo-python:latest

COPY . /root/zerotwo/
RUN  mkdir  /root/zerotwo/bin/
WORKDIR /root/zerotwo/

RUN pip3 install -r requirements.txt

CMD ["python3", "-m", "zerotwo"]