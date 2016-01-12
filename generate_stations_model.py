# -*- coding: utf-8 -*-
"""
Created on Tue Jan 12 13:16:13 2016

@author: alhamood
"""

import numpy as np
import pandas as pd
import seaborn as sbc
import simplejson as json
import os

Trip_Data = pd.read_csv('datafiles/Trip_Data.csv', index_col = 0)	
Trip_Data.index = pd.to_datetime(Trip_Data.index)

Weekday_Trip_Data = Trip_Data[Trip_Data['IsWeekday'].tolist()]

Weekends = np.invert(Trip_Data['IsWeekday'])
Weekend_Trip_Data = Trip_Data[Weekends.tolist()]

DailyStarts = pd.read_csv('~/Data Incubator/Capstone Project/Data/Cleaned CSVs/Bay/DailyStarts.csv', index_col = 0)
DailyStarts.index = pd.to_datetime(DailyStarts.index, infer_datetime_format=True)
DailyEnds = pd.read_csv('~/Data Incubator/Capstone Project/Data/Cleaned CSVs/Bay/DailyEnds.csv', index_col = 0)
DailyEnds.index = pd.to_datetime(DailyEnds.index, infer_datetime_format=True)

Station_Weekday_Hour_Totals = pd.DataFrame(index=range(24), columns=DailyStarts.keys())
for hour in range(24):
	hour_selector = (Weekday_Trip_Data.index.hour == hour).tolist()
	hour_trips = Weekday_Trip_Data[hour_selector]
	for station in DailyStarts.keys():
		station_selector = (hour_trips['Start Terminal'] == int(station)).tolist()
		Station_Weekday_Hour_Totals.loc[hour, station] = sum(station_selector)

Station_Weekend_Hour_Totals = pd.DataFrame(index=range(24), columns=DailyStarts.keys())
for hour in range(24):
	hour_selector = (Weekend_Trip_Data.index.hour == hour).tolist()
	hour_trips = Weekend_Trip_Data[hour_selector]
	for station in DailyStarts.keys():
		station_selector = (hour_trips['Start Terminal'] == int(station)).tolist()
		Station_Weekend_Hour_Totals.loc[hour, station] = sum(station_selector)		
		
Station_Weekday_Hour_End_Totals = pd.DataFrame(index=range(24), columns=DailyStarts.keys())
for hour in range(24):
	hour_selector = (Weekday_Trip_Data.index.hour == hour).tolist()
	hour_trips = Weekday_Trip_Data[hour_selector]
	for station in DailyStarts.keys():
		station_selector = (hour_trips['End Terminal'] == int(station)).tolist()
		Station_Weekday_Hour_End_Totals.loc[hour, station] = sum(station_selector)
		
Station_Weekend_Hour_End_Totals = pd.DataFrame(index=range(24), columns=DailyStarts.keys())
for hour in range(24):
	hour_selector = (Weekend_Trip_Data.index.hour == hour).tolist()
	hour_trips = Weekend_Trip_Data[hour_selector]
	for station in DailyStarts.keys():
		station_selector = (hour_trips['End Terminal'] == int(station)).tolist()
		Station_Weekend_Hour_End_Totals.loc[hour, station] = sum(station_selector)

Station_Weekday_Hour_Start_Factors = (Station_Weekday_Hour_Totals / (Station_Weekday_Hour_Totals.sum().sum()))
Station_Weekday_Hour_End_Factors = (Station_Weekday_Hour_End_Totals / (Station_Weekday_Hour_End_Totals.sum().sum()))

Station_Weekday_Hour_Start_Factors.to_csv('datafiles/Station_Weekday_Hour_Start_Factors.csv')
Station_Weekday_Hour_End_Factors.to_csv('datafiles/Station_Weekday_Hour_End_Factors.csv')

Station_Weekend_Hour_Start_Factors = (Station_Weekend_Hour_Totals / (Station_Weekend_Hour_Totals.sum().sum()))
Station_Weekend_Hour_End_Factors = (Station_Weekend_Hour_End_Totals / (Station_Weekend_Hour_End_Totals.sum().sum()))

Station_Weekend_Hour_Start_Factors.to_csv('datafiles/Station_Weekend_Hour_Start_Factors.csv')
Station_Weekend_Hour_End_Factors.to_csv('datafiles/Station_Weekend_Hour_End_Factors.csv')