import json
from django.shortcuts import render
from rest_framework.decorators import api_view
from rest_framework.response import Response
import requests
from .models import *
from background_task import background
from django.utils import timezone
from datetime import datetime
from background_task.models import Task
from django.db.models import Q

import pytz

# Create your views here.
Scheduled = "Scheduled"
Cancelled = "Cancelled"
Enroute = "On The Way!"
Landed = "Landed / Taxiing"
Unknown = "result unknown"
GateArrival = "Arrived / Gate Arrival"
Arrived = "Arrived / Delayed"
Delayed = "On The Way! / Delayed"
OnTime = "On The Way! / On Time"
sDelayed = "Scheduled / Delayed"
Taxing = "Taxiing / Left Gate"
Delay = "Delayed"
enDelay = "En Route / Delayed"
enOntime = "En Route / On Time"
typeSchedule = {"1": "departure","4":"before-departure" ,"2": "arrival", "3": "before-arrival"}

def convertTimezone(time,zone):

    # Create a datetime object from the given timestamp
    timestamp = datetime.strptime(time, "%Y-%m-%dT%H:%M:%SZ")

    # Specify the timezone for conversion (Europe/Copenhagen)
    target_timezone = pytz.timezone(zone)

    # Convert the timestamp to the target timezone
    converted_timestamp = timestamp.astimezone(target_timezone)

    # Extract the time from the converted timestamp
    converted_time = converted_timestamp.strftime("%H:%M")

    print(converted_time)
    return converted_time

def sendNotification(tk, message, typeSche):
    subtitle = ""
    content = ""
    time = message['scheduled_off']
    if message['estimated_off'] is not None:
        time = message['estimated_off'] 
    if typeSche == typeSchedule["4"]:
        terminal = ''
        if message['terminal_origin'] is not None:
            terminal = f"from terminal {message['terminal_origin']}"
        subtitle = f"{message['ident']} ({message['origin']['city']} - {message['destination']['city']})"
        content = f"Expected departure at {convertTimezone(time,message['origin']['timezone'])} {terminal}"

    elif typeSche == typeSchedule["1"]:
        terminal = ''
        if message['terminal_origin'] is not None:
            terminal = f"from terminal {message['terminal_origin']}"
        subtitle = f"{message['ident']} ({message['origin']['city']} - {message['destination']['city']})"
        content = f"Departure at {convertTimezone(time,message['origin']['timezone'])} {terminal}"

    elif typeSche == typeSchedule["2"]:
        time = message['scheduled_on']
        if message['estimated_on'] is not None:
            time = message['estimated_on']
        arrival = ''
        if message['arrival_delay'] > 60:
            arrival = f"({int(message['arrival_delay'] / 60)} min late)"
        terminal = ''
        if message['terminal_destination'] is not None:
            terminal = f"at terminal {message['terminal_destination']}"
        subtitle = f"{message['ident']} ({message['origin']['city']} - {message['destination']['city']})"
        content = f"Arrived at {convertTimezone(time,message['destination']['timezone'])} {arrival} {terminal}"

    elif typeSche == typeSchedule["3"]:
        time = message['scheduled_on']
        if message['estimated_on'] is not None:
            time = message['estimated_on']
        arrival = ''
        if message['arrival_delay'] > 60:
            arrival = f"({int(message['arrival_delay'] / 60)} min late)"
        terminal = ''
        if message['terminal_destination'] is not None:
            terminal = f"at terminal {message['terminal_destination']}"
        subtitle = f"{message['ident']} ({message['origin']['city']} - {message['destination']['city']})"
        content = f"Expected arrival at {convertTimezone(time,message['destination']['timezone'])} {arrival} {terminal}"



    print("Notification sent")
    url = "https://onesignal.com/api/v1/notifications"

    payload = {
        "app_id": "34091a03-24a4-4931-b7af-290a1081c021",
        "tags": [{"key": "device_token", "relation": "=", "value": tk}],
        "contents": {"en": content},
        "headings": {"en": "Flight Tracker"},
        "subtitle": {"en": subtitle},
        "ios_badgeType": "Increase",
        "ios_badgeCount": 1,
        "name": "INTERNAL_CAMPAIGN_NAME",
    }
    headers = {
        "accept": "application/json",
        "Authorization": "Basic YTMyMjQyMjMtZmJjYS00MWI1LThkMGItMjgxZGZhZGQ1NzM3",
        "content-type": "application/json",
    }

    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        return True
    else:
        return False


@api_view(["POST"])
def callback(request):
    try:
        print(request.POST)
        obj = Callback(data=str(json.dumps(request.POST)))
        obj.save()
    except Exception as e:
        print(e)

    try:
        obj = Callback(data=str(json.dumps(request.data)))
        obj.save()
        print(request.data)

    except Exception as e:
        print(e)
    return Response({"status": True})


@api_view(["POST"])
def enable_flight_track(request, flight, token):
    res = get_flight_status(flight)
    print(res)
    if res is not None and flight is not None and token is not None:
        current_time = timezone.now()

        data = res["flights"][0]
        print(data)
        if data["progress_percent"] is not None:
            # check departure not yet on time
            if data["progress_percent"] == 0 and Scheduled in data["status"]:
                print("in departure not yet")
                departure_time = datetime.strptime(
                    data["scheduled_out"], "%Y-%m-%dT%H:%M:%SZ"
                ).replace(tzinfo=timezone.utc)
                time_difference = departure_time - current_time
                time_difference_minutes = int(time_difference.total_seconds() / 60)
                if time_difference_minutes >= 15:
                    print("schedule 1")
                    schedule_flight_notifify(
                        typeSchedule["1"],
                        flight,
                        token,
                        schedule=timezone.timedelta(
                            minutes=time_difference_minutes - 15
                        ),
                    )

            elif data["progress_percent"] == 0 and sDelayed in data["status"]:
                print("in departure not yet & delayed")
                departure_time = datetime.strptime(
                    data["estimated_out"], "%Y-%m-%dT%H:%M:%SZ"
                ).replace(tzinfo=timezone.utc)
                time_difference = departure_time - current_time
                time_difference_minutes = int(time_difference.total_seconds() / 60)
                if time_difference_minutes >= 15:
                    print("schedule 2")
                    schedule_flight_notifify(
                        typeSchedule["1"],
                        flight,
                        token,
                        schedule=timezone.timedelta(
                            minutes=time_difference_minutes - 15
                        ),
                    )

            elif data["progress_percent"] > 0 and (
                Enroute in data["status"]
                or OnTime in data["status"]
                or enOntime in data["status"]
                or Delayed in data["status"]
                or enDelay in data["status"]
            ):
                print("in arrival")
                time = data["scheduled_in"]
                if data["estimated_in"] is not None:
                    time = data["estimated_in"]
                departure_time = datetime.strptime(time, "%Y-%m-%dT%H:%M:%SZ").replace(
                    tzinfo=timezone.utc
                )
                time_difference = departure_time - current_time
                time_difference_minutes = int(time_difference.total_seconds() / 60)
                print(time_difference_minutes)
                if time_difference_minutes >= 15:
                    print("schedule 3")
                    schedule_flight_notifify(
                        typeSchedule["3"],
                        flight,
                        token,
                        schedule=timezone.timedelta(
                            minutes=time_difference_minutes - 15
                        ),
                    )
                else:
                    schedule_flight_notifify(
                        typeSchedule["2"],
                        flight,
                        token,
                        schedule=timezone.timedelta(minutes=time_difference_minutes),
                    )
            return Response({"success": True, "message": "Alert Scheduled"})
        else:
            return Response(
                {
                    "success": False,
                    "message": "Alert cannot be schedule for this flight",
                }
            )
    else:
        return Response({"success": False, "message": "flight id, token required"})


@background
def schedule_flight_notifify(typeSche, flight, token):
    res = get_flight_status(flight)
    if res is not None:
        current_time = timezone.now()
        data = res["flights"][0]
        if typeSchedule["1"] == typeSche:
            print("notification ", result)
            if data["progress_percent"] == 0 and (
                Scheduled in data["status"] or sDelayed in data["status"]
            ):
                result = sendNotification(token, data, typeSchedule["4"])

                time = data["scheduled_in"]
                if data["estimated_in"] is not None:
                    time = data["estimated_in"]
                departure_time = datetime.strptime(time, "%Y-%m-%dT%H:%M:%SZ").replace(
                    tzinfo=timezone.utc
                )
                time_difference = departure_time - current_time
                time_difference_minutes = int(time_difference.total_seconds() / 60)
                schedule_flight_notifify(
                    typeSchedule["1"],
                    flight,
                    token,
                    schedule=timezone.timedelta(minutes=(time_difference_minutes + 3)),
                )
            elif data["progress_percent"] > 0 and (
                Enroute in data["status"]
                or OnTime in data["status"]
                or enOntime in data["status"]
                or Delayed in data["status"]
                or enDelay in data["status"]
            ):
                result = sendNotification(token, data, typeSchedule["1"])
                time = data["scheduled_in"]
                if data["estimated_in"] is not None:
                    time = data["estimated_in"]
                departure_time = datetime.strptime(time, "%Y-%m-%dT%H:%M:%SZ").replace(
                    tzinfo=timezone.utc
                )
                time_difference = departure_time - current_time
                time_difference_minutes = int(time_difference.total_seconds() / 60)
                if time_difference_minutes >= 15:
                    schedule_flight_notifify(
                        typeSchedule["2"],
                        flight,
                        token,
                        schedule=timezone.timedelta(
                            minutes=time_difference_minutes - 15
                        ),
                    )
                else:
                    schedule_flight_notifify(
                        typeSchedule["2"],
                        flight,
                        token,
                        schedule=timezone.timedelta(minutes=time_difference_minutes),
                    )
        elif typeSchedule["2"] == typeSche:
            if data["progress_percent"] == 100:
                sendNotification(token, data, typeSchedule["2"])
            else:
                time = data["scheduled_in"]
                if data["estimated_in"] is not None:
                    time = data["estimated_in"]
                departure_time = datetime.strptime(time, "%Y-%m-%dT%H:%M:%SZ").replace(
                    tzinfo=timezone.utc
                )
                time_difference = departure_time - current_time
                time_difference_minutes = int(time_difference.total_seconds() / 60)
                schedule_flight_notifify(
                    typeSchedule["2"],
                    flight,
                    token,
                    schedule=timezone.timedelta(minutes=(time_difference_minutes + 2)),
                )
        elif typeSchedule["3"] == typeSche:
            sendNotification(token, data, typeSchedule["3"])
            time = data["scheduled_in"]
            if data["estimated_in"] is not None:
                time = data["estimated_in"]
            departure_time = datetime.strptime(time, "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=timezone.utc
            )
            time_difference = departure_time - current_time
            time_difference_minutes = int(time_difference.total_seconds() / 60)
            schedule_flight_notifify(
                typeSchedule["2"],
                flight,
                token,
                schedule=timezone.timedelta(minutes=(time_difference_minutes + 2)),
            )


def get_flight_status(flight_id):
    # Make a request to the FlightAware Aero API to get flight information
    url = f"https://aeroapi.flightaware.com/aeroapi/flights/{flight_id}?ident_type=fa_flight_id"
    response = requests.get(
        url, headers={"x-apikey": "J7L39zngxhOfE32FiIVvpRXR2bwc4OPB"}
    )
    if response.status_code == 200:
        flight_info = response.json()
        return flight_info
    else:
        return None

@api_view(['POST'])
def deleteSchedule(request,flight,token):
    if token and flight:
        task = Task.objects.filter(Q(task_params__contains=flight) & Q(task_params__contains=token)).first()
        print(task)
        if task:
            task.delete()
            return Response({'status':True,'message':'deleted'})
        return Response({'status':False,'message':'not found'})
    return Response({'status':False,'message':'Something went wrong'})
