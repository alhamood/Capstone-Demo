# -*- coding: utf-8 -*-
"""
Created on Fri Jan  8 18:18:42 2016

@author: alhamood
"""

import numpy as np
import pandas as pd
import seaborn as sbc
import simplejson as json
import os

DailyStarts = pd.read_csv('~/Data Incubator/Capstone Project/Data/Cleaned CSVs/Bay/DailyStarts.csv', index_col = 0)
DailyStarts.index = pd.to_datetime(DailyStarts.index, infer_datetime_format=True)
DailyEnds = pd.read_csv('~/Data Incubator/Capstone Project/Data/Cleaned CSVs/Bay/DailyEnds.csv', index_col = 0)
DailyEnds.index = pd.to_datetime(DailyEnds.index, infer_datetime_format=True)
DailySums = np.sum(DailyStarts, axis=1)
DailyAvgStarts = (sum(DailyStarts.sum()))/float(len(DailyStarts))
AllTrips = pd.read_csv('~/Data Incubator/Capstone Project/Data/Bay Area/Combined CSVs/BayTrips_All.csv', index_col = 0)
AllTrips.index = pd.to_datetime(AllTrips.index, infer_datetime_format=True)
AllTrips = AllTrips[['Start Terminal', 'End Terminal']]
AllTrips['Zone'] = ''
stations = pd.read_csv('~/Data Incubator/Capstone Project/Data/Cleaned CSVs/Bay/201408_station_data.csv')
stations.index = stations['station_id']
for station in stations['station_id']:
	selector = (AllTrips['Start Terminal']==station).tolist()
	AllTrips.loc[selector, 'Zone'] = stations.loc[station, 'landmark']
	
Weekdays = [False] * len(AllTrips.index)
for t_index, trip in enumerate(AllTrips.index):
	if trip.weekday() < 5:
		Weekdays[t_index] = True
		
AllTrips['IsWeekday'] = Weekdays

AllTrips.to_csv('/Users/alhamood/Data Incubator/Capstone Project/Demo/datafiles/Trip_Data.csv')

#with open('/Users/alhamood/Data Incubator/Capstone Project/Demo/datafiles/TripTimes.json', 'w') as outfile:
#	json.dump(triptimes, outfile)

# First find overall effect factors for each day of the week
Day_of_Week = pd.DataFrame([day.weekday() for day in DailySums.index])
DoW_Totals = [np.NaN]*7
for day in range(7):
	selector = (Day_of_Week==day).values.tolist()
	DoW_Totals[day] = sum(DailyStarts[selector].sum(axis=1))
DoW_Factors = [DoW_Totals[day]/(float(sum(DoW_Totals))/7) for day in range(7)]
	
	
# Zone factors
Zones = AllTrips['Zone'].unique()
Zone_Totals = [np.NaN]*5
for index, zone in enumerate(Zones):
	selector = (AllTrips['Zone']==zone).values.tolist()
	Zone_Totals[index] = sum(selector)
Zone_Factors = [Zone_Totals[zone]/(float(sum(Zone_Totals))/5) for zone in range(5)]
	
# Then month factors
Month = pd.DataFrame([day.month for day in DailySums.index])
Month_Totals = [np.NaN]*12
for month in range(1, 13):
	selector = (Month==month).values.tolist()
	Month_Totals[month-1] = sum(DailyStarts[selector].sum(axis=1))
Month_Factors = [Month_Totals[month-1]/(float(sum(Month_Totals))/12) for month in range(1,13)]

# Hourly factors, weekdays
Start_Hours = pd.to_datetime(AllTrips.index).hour
Hour_Totals = [np.NaN]*24
for hour in range(24):
	selector = (Start_Hours==hour) 
	selector = (selector & AllTrips['IsWeekday']).tolist()
	Hour_Totals[hour] = sum(selector)
Hour_Factors_Weekdays = [Hour_Totals[hour]/(float(sum(Hour_Totals))/24) for hour in range(24)]

# Hourly factors, weekends
Start_Hours = pd.to_datetime(AllTrips.index).hour
Hour_Totals = [np.NaN]*24
for hour in range(24):
	selector = (Start_Hours==hour) 
	selector = (selector & np.invert(AllTrips['IsWeekday'])).tolist()
	Hour_Totals[hour] = sum(selector)
Hour_Factors_Weekends = [Hour_Totals[hour]/(float(sum(Hour_Totals))/24) for hour in range(24)]

# Hourly factors
Start_Hours = pd.to_datetime(AllTrips.index).hour
Hour_Totals = [np.NaN]*24
for hour in range(24):
	selector = (Start_Hours==hour).tolist()
	Hour_Totals[hour] = sum(selector)
Hour_Factors = [Hour_Totals[hour]/(float(len(Start_Hours))/24) for hour in range(24)]

days=pd.date_range(min(DailyStarts.index), max(DailyStarts.index))
day_residuals = []

for test_date in days:
	test_date = pd.to_datetime(test_date)
	test_date_starts = DailyStarts[DailyStarts.index.date==test_date.date()]
	test_date_total = sum(test_date_starts.sum())
	test_date_prediction = DailyAvgStarts * DoW_Factors[test_date.weekday()] * Month_Factors[test_date.month-1]
	test_date_residual = test_date_total/test_date_prediction
	day_residuals.append(test_date_residual)
day_residuals = pd.DataFrame(data=day_residuals, index=days)

#with open('/Users/alhamood/Data Incubator/Capstone Project/Demo/datafiles/DoW_Factors.json', 'w') as outfile:
#	json.dump(DoW_Factors, outfile)
	
#DoW_Factors.to_csv('/Users/alhamood/Data Incubator/Capstone Project/Demo/datafiles/DoW_Factors.csv')	
with open('/Users/alhamood/Data Incubator/Capstone Project/Demo/datafiles/Month_Factors.json', 'w') as outfile:
	json.dump(Month_Factors, outfile)
#DoW_Factors.to_csv('/Users/alhamood/Data Incubator/Capstone Project/Demo/datafiles/Month_Factors.csv')	

with open('/Users/alhamood/Data Incubator/Capstone Project/Demo/datafiles/Hour_Factors.json', 'w') as outfile:
	json.dump(Hour_Factors, outfile)
	
with open('/Users/alhamood/Data Incubator/Capstone Project/Demo/datafiles/Hour_Factors_Weekdays.json', 'w') as outfile:
	json.dump(Hour_Factors_Weekdays, outfile)

with open('/Users/alhamood/Data Incubator/Capstone Project/Demo/datafiles/Hour_Factors_Weekends.json', 'w') as outfile:
	json.dump(Hour_Factors_Weekends, outfile)	
	
#DoW_Factors.to_csv('/Users/alhamood/Data Incubator/Capstone Project/Demo/datafiles/Hour_Factors.csv')	
	
with open('/Users/alhamood/Data Incubator/Capstone Project/Demo/datafiles/Daily_Avg_Starts.json', 'w') as outfile:
	json.dump(DailyAvgStarts, outfile)
	
with open('/Users/alhamood/Data Incubator/Capstone Project/Demo/datafiles/Zone_Factors.json', 'w') as outfile:
	json.dump(Zone_Factors, outfile)

day_residuals.to_csv('/Users/alhamood/Data Incubator/Capstone Project/Demo/datafiles/Day_Residuals.csv')