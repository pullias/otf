import requests
import json

from getpass import getpass

import numpy as np
import pandas as pd
import plotly.express as px
from pprint import pprint

def get_credentials():
    """
    Prompt the user to enter their credentials
    """
    email = input("Enter the email address associated with your OT Account: ")
    password = getpass("Enter the password associated with your account: (Hidden for Security): ")
    return email, password

def get_workout_data(email, password):
    """
    Leverage previous work to make HTTP Requests to the OFT Endpoint
    """

    header = '{"Content-Type": "application/x-amz-json-1.1", "X-Amz-Target": "AWSCognitoIdentityProviderService.InitiateAuth"}'
    body = '{"AuthParameters": {"USERNAME": "'+email+'", "PASSWORD": "'+password+'"}, "AuthFlow": "USER_PASSWORD_AUTH", "ClientId": "65knvqta6p37efc2l3eh26pl5o"}'

    header = json.loads(header)
    body = json.loads(body)

    response = requests.post("https://cognito-idp.us-east-1.amazonaws.com/", headers=header, json=body)

    token = json.loads(response.content)['AuthenticationResult']['IdToken']

    endpoint = "https://api.orangetheory.co/virtual-class/in-studio-workouts"
    header = {"Content-Type": "application/json", "Authorization": token, "Connection": "keep-alive", "accept": "appliction/json", "accept-language": "en-US,en;q=0.9", "origin": "https://otlive.orangetheory.com", "referer": "https://otlive.orangetheory.com", "sec-ch-ua": '".Not/A)Brand";v="99", "Google Chrome";v="103", "Chromium";v="103"', "sec-ch-ua-platform": '"macOS"', "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36"}

    response = requests.get(endpoint, headers=header)
    class_data_json_response = json.loads(response.content)

    member_uuid = class_data_json_response['data'][0]['memberUuId']
    endpoint = "https://api.orangetheory.co/member/members/"+member_uuid+"?include=memberClassSummary"
    response = requests.get(endpoint, headers=header)
    member_data_json_response  = json.loads(response.content)['data']

    return class_data_json_response, member_data_json_response


def extract_minute_by_minute_data(json_response, cutoff_percentile=0.1):
    """
    Extracts out the minute by minute hr data, aligns dataset so all classes have same length (short classes dropped),
    and returns the "usable" data for further analysis

    Arguments:
        json_response: JSON Response from the endpoint to iterate through
        cutoff_percentile (optional): What percentile of num_minutes to use for data alignment

    Returns:
        numpy array where row-wise is classes, column-wise is heart rate at a given minute
        cutoff: the computed cutoff value
    """
    # We'll trim our heart rate data to the lower 25th quantile. This will account for 
    # some of the irregularity in when class starts without dropping us to those 45 min classes (unless you do a lot of those)
    num_mins_in_class = []
    hr_data = []
    for item in json_response['data']:
        try:
            # Security hole
            hr_as_lst = eval(item["minuteByMinuteHr"])
            num_mins = len(hr_as_lst)
            num_mins_in_class.append(num_mins)
            hr_data.append(hr_as_lst)
        except KeyError:
            print(item.keys())

    # Dyanmic cutoff application - Must have at least 10th percentile minutes in the class
    cutoff = int(np.floor(np.quantile(np.asarray(num_mins_in_class), cutoff_percentile)))
    usable_minute_by_minutes = []
    for row in hr_data:
        if len(row) < cutoff:
            continue
        usable_minute_by_minutes.append(row[:cutoff])
    heartrate_arr = np.asarray(usable_minute_by_minutes)
    return heartrate_arr, cutoff

def extract_class_type_data(json_response):
    """
    Extract the class type data from json

    Arguments:
        json_response: JSON Response from the endpoint to iterate through
    """
    class_type_counter = {}
    for item in json_response['data']:
        if item['classType'] == None:
            item['classType'] = "No Class Type Found"
        if item['classType'] in class_type_counter:
            class_type_counter[item['classType']] = class_type_counter[item['classType']] + 1
        else: 
            class_type_counter[item['classType']] = 1
    return class_type_counter

def extract_class_coach_data(json_response):
    """
    Extract the class coach data from json

    Arguments:
        json_response: JSON Response from the endpoint to iterate through
    """
    class_coach_counter = {}
    for item in json_response['data']:
        coach = (item['coach'] if 'coach' in item and item['coach'] is not None else "NoCoach") + \
            " - " + (item['studioName'] if 'studioName' in item and item['studioName'] is not None else "NoStudio")
        if coach in class_coach_counter:
            class_coach_counter[coach] = class_coach_counter[coach] + 1
        else:
            class_coach_counter[coach] = 1
    return class_coach_counter

def extract_member_data(json_response):
    """
    Parse through the member data json response
    """
    member_data = {}
    member_data["Home Studio"] = str(json_response['homeStudio']['studioName'])
    member_data["Total classes booked"] = str(json_response['memberClassSummary']['totalClassesBooked'])
    member_data["Total classes attended"] = str(json_response['memberClassSummary']['totalClassesAttended'])
    member_data["Total intro classes"] = str(json_response['memberClassSummary']['totalIntro'])
    member_data["Total OT Live classes booked"] = str(json_response['memberClassSummary']['totalOTLiveClassesBooked'])
    member_data["Total OT Live classes attended"] = str(json_response['memberClassSummary']['totalOTLiveClassesAttended'])
    member_data["Total classes used HRM"] = str(json_response['memberClassSummary']['totalClassesUsedHRM'])
    member_data["Total studios visited"] = str(json_response['memberClassSummary']['totalStudiosVisited'])
    member_data["Max HR"] = str(json_response['maxHr'])
    return member_data

def segment_starting_station(heartrate_arr, cutoff):
    """
    Convert the array into a pandas dataframe, then segment into data where we believe the 
    individual started on the tread vs started on the rower

    Arguments:
        heartrate_arr: Numpy array of heart rate minute by minute data
        cutoff: The previously computed cutoff value for class length in minutes

    Returns:
        df_tread_to_start: DataFrame where the user started on tread
        df_row_to_start: DataFrame where the user started on the rower

    Notes:
        The assumption here is that the user will have their highest heartrate occur while on the tread
    """

    # Convert to a dataframe so we can get some easy stats and visualize
    df = pd.DataFrame(heartrate_arr)

    # But first we want to have separate graphs for classes where you start tread vs rower
    # Sorry 3G! This works by assuming your max heart rate occurs when treading
    class_midpoint = cutoff // 2
    # print(df.idxmax(axis=1))
    df_tread_to_start = df[df.idxmax(axis=1) < class_midpoint]
    df_row_to_start = df[df.idxmax(axis=1) >= class_midpoint]

    return df_tread_to_start, df_row_to_start

def plot_heartrate_over_time(df, title=""):
    """
    Create an interactive plot of heart rate vs time. Show mean, and the 25th+75th percentiles

    Arguments:
        df: Dataframe containing heartrate data (preferably segmented)

    """
    # Get the number of classes in our dataset
    num_classes = df.shape[0]

    # Compute summary statistics for plotting
    df_summary = df.describe().transpose()

    # Generate plot and show to user
    fig = px.line(
        df_summary, 
        x=df_summary.index, 
        y=["mean","25%","75%"], 
        title=f"{title}:{num_classes}",
    )
    fig.show()

def plot_bar_chart(dictionary, title=""):
    """
    Takes any of the arbitrary dictionaries and plots them as bar plot
    """
    fig = px.bar(x=dictionary.keys(), y=dictionary.values(), title=title)
    fig.show()

if __name__ == "__main__":
    from pprint import pprint

    workout_data_json, member_data_json = get_workout_data(*get_credentials())
    usable_minute_by_minutes, cutoff = extract_minute_by_minute_data(workout_data_json)
    df_tread_to_start, df_row_to_start = segment_starting_station(usable_minute_by_minutes, cutoff)
    plot_heartrate_over_time(df_tread_to_start, "Tread Start Heartrate Progressionn<br>Num Classes")
    plot_heartrate_over_time(df_row_to_start, "Row Start Heartrate Progressionn<br>Num Classes")
    
    data = extract_member_data(member_data_json)
    pprint(data)

    data = extract_class_coach_data(workout_data_json)
    plot_bar_chart(data, "Class By Coach")

    data = extract_class_type_data(workout_data_json)
    plot_bar_chart(data, "Class By Type")


    # Get the derivative of your heart rate at each point in the workout. Since our delta_t = 1 diff will work just fine
    first_deriv_arr = np.diff(usable_minute_by_minutes, 1, axis=1)

    # Values of 1 indicate regions where the heart rate increases, 0 are decreases
    heart_rate_increasing_decreasing_mask = np.diff(usable_minute_by_minutes) < 0
    
# # Code from Original Work

# hrTotals = {}
# minCount = {}
# secsInZone = {"Red": 0, "Orange": 0, "Green": 0, "Blue": 0, "Black": 0}
# dataClassCounter = 0
# maxHrAverageTotal = 0
# averageHrTotal = 0
# averageSplatsTotal = 0
# averageCaloriesTotal = 0
# for workout in inStudioResponse_json['data']:
#     dataClassCounter = dataClassCounter + 1
#     count = 1
#     if 'minuteByMinuteHr' in workout and workout['minuteByMinuteHr'] is not None:
#         for hr in workout['minuteByMinuteHr'].split("[")[1].split("]")[0].split(","):
#             if count in hrTotals:
#                 hrTotals[count] = int(hrTotals[count]) + int(hr)
#             else:
#                 hrTotals[count] = int(hr)
#             if count in minCount:
#                 minCount[count] = minCount[count] + 1
#             else:
#                 minCount[count] = 1
#             count = count + 1
#     secsInZone['Red'] = secsInZone['Red'] +workout['redZoneTimeSecond']
#     secsInZone['Orange'] = secsInZone['Orange'] + workout['orangeZoneTimeSecond']
#     secsInZone['Green'] = secsInZone['Green'] + workout['greenZoneTimeSecond']
#     secsInZone['Blue'] = secsInZone['Blue'] + workout['blueZoneTimeSecond']
#     secsInZone['Black'] = secsInZone['Black'] + workout['blackZoneTimeSecond']
#     maxHrAverageTotal = maxHrAverageTotal + workout['maxHr']
#     averageHrTotal = averageHrTotal + workout['avgHr']
#     averageSplatsTotal = averageSplatsTotal + workout['totalSplatPoints']
#     averageCaloriesTotal = averageCaloriesTotal + workout['totalCalories']

# print("The remainder of the data is based on workout summaries available. You have " + str(dataClassCounter) + " workouts with data available")
# print("Average Max HR: " + str(maxHrAverageTotal / dataClassCounter))
# print("Average HR: " + str(averageHrTotal / dataClassCounter))
# print("Average Splats: " + str(averageSplatsTotal / dataClassCounter))
# print("Average calorie burn: "+ str(averageCaloriesTotal / dataClassCounter))

# print("Average HR by Min:")
# for min in minCount:
#     average = hrTotals[min] / minCount[min]
#     stringBuilder = str(min)+": "+str(average)
#     print(stringBuilder)
# print("Average time in each zone (Mins)")
# print("Red: "+str(secsInZone['Red']/dataClassCounter/60))
# print("Orange: "+str(secsInZone['Orange']/dataClassCounter/60))
# print("Green: "+str(secsInZone['Green']/dataClassCounter/60))
# print("Blue: "+str(secsInZone['Blue']/dataClassCounter/60))
# print("Black: "+str(secsInZone['Black']/dataClassCounter/60))
