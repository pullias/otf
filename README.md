# OTF Wrapped (Unofficial)
Everyone loves Spotify Wrapped, so why shouldn't we get an OTF variant?! This script is a proof of concept for just that. It connects directly to Orange Theory's AWS endpoint and pulls your data; note that this  authenticates with your email and password associated with your OTF account. From there, the script collects your data and presents it to you!

## What's included
* Automatically determines tread start vs row start (assumes max HR occurs in your tread block) and plots your typical class
* Minutes spent in each HR zone over the course of the year
* Total Calories burned
* Max Calories burned in a single class
* Max Splats in a single class
* Max HR seen in a single class
* How many of each class type you attended
* The week you attended the most classes
* How many classes you took with each coach
* Overall number of classes you've taken

## How to run it
You're going to need:
* A valid [python](https://www.python.org/downloads/) installation on your computer
* Install the required packages: `pip install -r requirements.txt`
* Run the script in terminal: `python __init__.py`

## Known Issues + Future Improvements
* Most of the data is time-boxed to 2023. Some plots (HR minute by minute) include all of your data
* Any semblance of aesthetic. I'm a Data Scientist, not a Designer. I welcome anyone to create a prettier version of this. Bonus points if you want to take on making an `exe` version for those who don't want to use `python`
* HR Recovery Analysis - Originally I wanted to use the minute by minute HR data to analyze how quickly your HR increases/decreases since this recovery time is a huge part of OT. Don't currently have the time right now to devote to this. Also 1 min resolution is pretty coarse for this type of analysis.

## Special Thanks
Big thanks to `/u/fireislander` on Reddit for all the footwork to get the data from OTF's AWS Endpoint.