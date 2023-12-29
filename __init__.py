import requests
import json

from getpass import getpass

import mistune
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio

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

def extract_zones_splats_calories(json_response):
    """
    Extracts the second level zone data, splats per class, and calories
    """
    seconds_in_zone_splats_calories = {
        "black": [],
        "blue": [],
        "green": [],
        "orange": [],
        "red": [],
        "splats": [],
        "calories": [],
        "max_hr": [],
        "date": []
    }
    for workout in json_response["data"]:
        seconds_in_zone_splats_calories["black"].append(workout["blackZoneTimeSecond"])
        seconds_in_zone_splats_calories["blue"].append(workout["blueZoneTimeSecond"])
        seconds_in_zone_splats_calories["green"].append(workout["greenZoneTimeSecond"])
        seconds_in_zone_splats_calories["orange"].append(workout["orangeZoneTimeSecond"])
        seconds_in_zone_splats_calories["red"].append(workout["redZoneTimeSecond"])
        seconds_in_zone_splats_calories["splats"].append(workout["totalSplatPoints"])
        seconds_in_zone_splats_calories["calories"].append(workout["totalCalories"])
        seconds_in_zone_splats_calories["max_hr"].append(workout["maxHr"])
        seconds_in_zone_splats_calories["date"].append(workout["classDate"])
    
    # Get our data into a dataframe and return for further analysis
    df = pd.DataFrame.from_dict(seconds_in_zone_splats_calories)
    df["timestamp"] = pd.to_datetime(df["date"])

    return df

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
        y=["mean"], 
        title=f"{title}:{num_classes}",
    )
    fig.add_trace(go.Scatter(
        x=df_summary.index, 
        y=df_summary["25%"], 
        fill='tonexty', 
        fillcolor='rgba(25,36,181,0.2)',                 
        line=dict(color='rgba(255,255,255,0)'),
        name='25th percentile')
    )
    fig.add_trace(go.Scatter(
        x=df_summary.index, 
        y=df_summary["75%"], 
        fill='tonexty', 
        fillcolor='rgba(32,46,245,0.2)',
        line=dict(color='rgba(255,255,255,0)'),
        name='75th percentile')
    )
    fig.update_layout(
        xaxis_title='Minutes into Class (min)',
        yaxis_title='Heart Rate (BPM)'
    )
    return fig

def plot_bar_chart(dictionary, title="", xaxis_title="", yaxis_title=""):
    """
    Takes any of the arbitrary dictionaries and plots them as bar plot
    """
    fig = px.bar(x=dictionary.keys(), y=dictionary.values(), title=title)
    if xaxis_title:
        fig.update_layout(xaxis_title=xaxis_title)
    if yaxis_title:
        fig.update_layout(yaxis_title=yaxis_title)
    return fig

def markdown_to_html(template_str, output_file):
    """
    Create an HTML output from our templated markdown
    """
    # Convert Markdown to HTML
    html = mistune.markdown(template_str, escape=False)

    # Write the HTML content to the output file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)

if __name__ == "__main__":

    workout_data_json, member_data_json = get_workout_data(*get_credentials())
    usable_minute_by_minutes, cutoff = extract_minute_by_minute_data(workout_data_json)
    df_tread_to_start, df_row_to_start = segment_starting_station(usable_minute_by_minutes, cutoff)
    tread_start_plot = plot_heartrate_over_time(df_tread_to_start, "Average Tread Start Heartrate Progressionn<br>Num Classes")
    tread_start_plot = pio.to_html(tread_start_plot, include_plotlyjs=True, full_html=False)
    
    row_start_plot = plot_heartrate_over_time(df_row_to_start, "Average Row Start Heartrate Progressionn<br>Num Classes")
    row_start_plot = row_start_plot.to_html(full_html=False)

    data = extract_member_data(member_data_json)
    class_count = data["Total classes attended"]

    data = extract_class_coach_data(workout_data_json)
    class_by_coach_plot = plot_bar_chart(data, "Class By Coach (It's okay, everyone has favorites!)", xaxis_title="Coach", yaxis_title="Classes Taken (#)")
    class_by_coach_plot = class_by_coach_plot.to_html(full_html=False)

    data = extract_class_type_data(workout_data_json)
    class_by_type_plot = plot_bar_chart(data, "Class By Type (When was your last 90 min or Tornado?!)", xaxis_title="Class Type", yaxis_title="Classes Taken (#)")
    class_by_type_plot = class_by_type_plot.to_html(full_html=False)

    df_class_data = extract_zones_splats_calories(workout_data_json)
    df_class_data = df_class_data[df_class_data["timestamp"] > pd.to_datetime("2023-01-01 00:00:00+00:00")]
    df_class_data = df_class_data[df_class_data["timestamp"] < pd.to_datetime("2024-01-01 00:00:00+00:00")]

    # Let's see what week we had the most classes
    # Set 'timestamp' as the index
    df_class_data.set_index('timestamp', inplace=True)

    # Resample on a weekly basis and get counts
    weekly_counts = df_class_data.resample('W').size()

    # Convert the series to a DataFrame
    weekly_counts_df = pd.DataFrame(weekly_counts, columns=['count'])

    # Find the timestamp where the max count occurs
    max_count_timestamp = weekly_counts.idxmax()
    max_count_value = weekly_counts.loc[max_count_timestamp]

    # Get the corresponding row from the original DataFrame
    max_count_row = weekly_counts_df.loc[weekly_counts_df.index.isin([max_count_timestamp])]

    # See what's the most calories, splats, and peak HR you had
    max_splats = df_class_data["splats"].max()
    max_calories = df_class_data["calories"].max()
    total_calories = df_class_data["calories"].sum()
    max_hr = df_class_data["max_hr"].max()

    # Calculate out number of minutes spent in each zone
    df_zone_data = df_class_data[["black", "blue", "green", "orange", "red"]]
    df_zone_data = df_zone_data/60.0
    df_zone_data = df_zone_data.sum(axis=0)
    minutes_in_zone_plot = plot_bar_chart(df_zone_data.to_dict(), "Minutes in Each Zone (Where did you spend the most time?)", xaxis_title="Zone", yaxis_title="Minutes (min)")
    minutes_in_zone_plot = minutes_in_zone_plot.to_html(full_html=False)

    with open("template.md", "r") as f:
        template_str = f.read()
    template_str = template_str.replace("{row_start_plot}", row_start_plot)
    template_str = template_str.replace("{tread_start_plot}", tread_start_plot)
    template_str = template_str.replace("{minutes_in_zone_plot}", minutes_in_zone_plot)
    template_str = template_str.replace("{total_calories}", str(total_calories))
    template_str = template_str.replace("{max_calories}", str(max_calories))
    template_str = template_str.replace("{max_splats}", str(max_splats))
    template_str = template_str.replace("{max_hr}", str(max_hr))
    template_str = template_str.replace("{class_by_type_plot}", class_by_type_plot)
    template_str = template_str.replace("{max_count_timestamp}", str(max_count_timestamp)[:10])
    template_str = template_str.replace("{max_count_value}", str(max_count_value))
    template_str = template_str.replace("{class_by_coach_plot}", class_by_coach_plot)
    template_str = template_str.replace("{class_count}", str(class_count))

    # Replace 'input.md' and 'output.html' with your file names
    markdown_to_html(template_str, 'otf_wrapped.html')

    # Get the derivative of your heart rate at each point in the workout. Since our delta_t = 1 diff will work just fine
    first_deriv_arr = np.diff(usable_minute_by_minutes, 1, axis=1)

    # Values of 1 indicate regions where the heart rate increases, 0 are decreases
    heart_rate_increasing_decreasing_mask = np.diff(usable_minute_by_minutes) < 0

    
    
