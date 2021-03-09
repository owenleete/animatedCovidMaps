#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Mar  5 08:40:30 2021

@author: owen
"""


import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import geopandas
import requests
import datetime

# Read in shapefile
counties = geopandas.read_file('countyShapefiles/UScounties.shp')

####################################################################
# Rename counties that have changed since the shapefile was created
####################################################################
counties.at[422,'NAME'] = 'Oglala Lakota County'
counties.at[422,'FIPS'] = '46102'
counties.at[422,'CNTY_FIPS'] = '102'

counties.at[3112,'NAME'] = 'Kusilvak Census Area'
counties.at[3112,'FIPS'] = '02158'
counties.at[3112,'CNTY_FIPS'] = '158'

counties.at[3122,'NAME'] = 'Petersburg Borough'
counties.at[3122,'FIPS'] = '02195'
counties.at[3122,'CNTY_FIPS'] = '195'

counties.at[3124,'NAME'] = 'Prince of Wales-Hyder Census Area'
counties.at[3124,'FIPS'] = '02198'
counties.at[3124,'CNTY_FIPS'] = '198'

counties.at[3136,'NAME'] = 'Hoonah-Angoon Census Area'
counties.at[3136,'FIPS'] = '02105'
counties.at[3136,'CNTY_FIPS'] = '105'
####################################################################

# Separate into contiguous, Alaska, and Hawaii
alaska = counties[counties['STATE_FIPS'].isin(['02'])]
hawaii = counties[counties['STATE_FIPS'].isin(['15'])]
contig = counties[~counties['STATE_FIPS'].isin(['02','15'])]

# Shift and scale Alaska to fit under California
alaska2 = alaska.copy()
alaska2.geometry = alaska.geometry.scale(0.3,0.5,0.5,origin=(-155,61,0))
alaska3 = alaska2.copy()
alaska3.geometry = alaska2.geometry.translate(38,-36,0)

map2 = pd.concat([contig, alaska3])

# Shift and scale Alaska to fit under Texas
hawaii2 = hawaii.copy()
hawaii2.geometry = hawaii.geometry.scale(1.5,1.5,1,origin=(-157,20.5,0))
hawaii3 = hawaii2.copy()
hawaii3.geometry = hawaii2.geometry.translate(56,3,0)

# Group all counties together, set fips as index
counties = pd.concat([map2, hawaii3])
counties.rename(columns={'FIPS':'fips'},inplace=True)
counties.set_index('fips',inplace=True)

# Download county population data from the census website
req_url = 'https://api.census.gov/data/2019/pep/population?get=DATE_DESC,DENSITY,POP,NAME&DATE_CODE=12&for=COUNTY'
response=requests.get(req_url)
pop_temp=response.json()
pop_data=pd.DataFrame(pop_temp[1:], columns=pop_temp[0])
pop_data['fips']=pop_data.state+pop_data.county
pop_data=pop_data.astype(dtype={'DENSITY':'float64','POP':'int64'})
pop_data.set_index('fips',inplace=True)
pop_data.drop(columns=['DATE_DESC','DATE_CODE','state','county'],inplace=True)
pop_data.rename(columns={'DENSITY':'density',"POP": "population"},inplace=True)

# create DF for cases and add population
cases = counties.copy()
cases = cases.join(pop_data[['population']], on='fips')

# Download case data from the NYT github
url = 'https://raw.githubusercontent.com/nytimes/covid-19-data/master/us-counties.csv'
caseData = pd.read_csv(url, converters={'fips': str})
caseData.set_index('fips',inplace=True)


# loop over days to create wide DF of cumulative cases by county
start_date = datetime.date(2020, 1, 21)
end_date = datetime.date(2021, 3, 3)
delta = datetime.timedelta(days=1)
while start_date <= end_date:
    temp = caseData.loc[caseData['date'] == str(start_date)].copy()
    temp.drop(columns=['date', 'county', 'state', 'deaths'],inplace=True)
    temp.rename(columns={'cases':str(start_date)},inplace=True)
    cases = cases.join(temp[str(start_date)], on='fips')
    start_date += delta
cases.fillna(0,inplace=True)

# Get number of daily cases as proportion of the population
newCases = pd.DataFrame(index=cases.index)
start_date = datetime.date(2020, 1, 21)
end_date = datetime.date(2021, 3, 2)
delta = datetime.timedelta(days=1)
while start_date <= end_date:
    newCases[str(start_date)] = cases[str(start_date+delta)]-cases[str(start_date)]
    newCases[str(start_date)] = newCases[str(start_date)].clip(lower=0)
    newCases[str(start_date)] = newCases[str(start_date)]/cases['population']
    start_date += delta
    
# Take rolling mean over 7 days to smooth day-of-week effects
temp = newCases.transpose()
for column in temp:
    temp[column] = temp[column].rolling(window=7,center=False).mean()

# create DF of cases per day
dailyCases = counties.copy()
start_date = datetime.date(2020, 1, 27)
end_date = datetime.date(2021, 3, 2)
delta = datetime.timedelta(days=1)
while start_date <= end_date:
    dailyCases = dailyCases.join(newCases[str(start_date)], on='fips')
    start_date += delta

# create plots of cases for each day
output_path = 'dailyCases'
start_date = datetime.date(2020, 1, 27)
end_date = datetime.date(2021, 3, 2)
delta = datetime.timedelta(days=1)
while start_date <= end_date:
    fig = dailyCases.plot(column=str(start_date), cmap='plasma', figsize=(10,6), linewidth=0.0, edgecolor='0.8', vmin=0, vmax=.0025, 
                       legend=True, norm=plt.Normalize(vmin=0, vmax=.0025)) # capped daily increase to be max 0.0025 or 0.25% per day 
                                                                            # to allow for more dynamic range in the common lower rates
    # remove axis of chart
    fig.axis('off')
    
    # add a title
    fig.set_title('Daily cases per capita', \
              fontdict={'fontsize': '20',
                         'fontweight' : '3'})
    
    # position the annotation to the bottom left
    fig.annotate(start_date.strftime("%b, %Y"),
            xy=(-70, 22),
            horizontalalignment='right', verticalalignment='bottom',
            fontsize=14)
    
    # save the figure png in the output path
    filepath = os.path.join(output_path, str(start_date)+'_.png')
    chart = fig.get_figure()
    chart.savefig(filepath, dpi=150)
    plt.close(chart)
    start_date += delta


### The following code uses imagemagik to convert the ficures into an animated gif and conver the gif into a smaller .mp4
### Run within directory containing plots
# convert -delay 5 -loop 1 202*.png dailyCases.gif
# ffmpeg -i dailyCases.gif -movflags faststart -pix_fmt yuv420p -vf "scale=trunc(iw/2)*2:trunc(ih/2)*2" dailyCases.mp4




movement = counties.set_index('STATE_NAME').copy()

# Read in movement data from the google community mobility reports
googleMovement = pd.read_csv('2020_US_Region_Mobility_Report.csv',converters={'census_fips_code': str})
googleMovement.rename(columns={'census_fips_code':'fips','sub_region_1':'STATE_NAME'},inplace=True)
googleMovement.dropna(subset=['iso_3166_2_code'],inplace=True)
googleMovement.set_index('STATE_NAME',inplace=True)

# Create DF with just retail and recreation change
start_date = datetime.date(2020, 2, 15)
gMove = googleMovement.loc[googleMovement['date'] == str(start_date)].copy()
gMove.drop(columns=['country_region_code','country_region','sub_region_2','metro_area','iso_3166_2_code','fips','place_id','grocery_and_pharmacy_percent_change_from_baseline','parks_percent_change_from_baseline','transit_stations_percent_change_from_baseline','workplaces_percent_change_from_baseline','residential_percent_change_from_baseline'],inplace=True)
gMove.rename(columns={'retail_and_recreation_percent_change_from_baseline':str(start_date)},inplace=True)

# populate DF with daily retail and recreation change
start_date = datetime.date(2020, 2, 16)
end_date = datetime.date(2021, 2, 27)
delta = datetime.timedelta(days=1)
while start_date <= end_date:
    temp = googleMovement.loc[googleMovement['date'] == str(start_date)].copy()
    temp.rename(columns={'retail_and_recreation_percent_change_from_baseline':str(start_date)},inplace=True)
    gMove = gMove.join(temp[str(start_date)], on='STATE_NAME')
    start_date += delta
    
# Create multi-index
gMove = gMove.reset_index()
gMove.set_index(['STATE_NAME','date'],inplace=True)

# Take rolling mean over 7 days to smooth day-of-week effects
temp = gMove.transpose()
for column in temp:
    temp[column] = temp[column].rolling(window=7,center=False).mean()  
gMove = gMove.reset_index()
gMove.set_index(['STATE_NAME'],inplace=True)

# Join movement data to counties by state
### This would probably be better with a state shapefile rather than a county shapefile, but I didn't want to deal with Alaska and Hawaii again
movement = movement.join(gMove, on='STATE_NAME')
      
# create mobility plots for each day
output_path = 'gMovementMap'
start_date = datetime.date(2020, 2, 21)
end_date = datetime.date(2021, 2, 27)
delta = datetime.timedelta(days=1)
while start_date <= end_date:
    fig = movement.plot(column=str(start_date), cmap='plasma', figsize=(10,6), linewidth=0.0, edgecolor='0.8', vmin=-70, vmax=10, 
                       legend=True, norm=plt.Normalize(vmin=-70, vmax=10)) #
    
    # remove axis of chart
    fig.axis('off')
    
    fig.set_title('Percent mobility change from baseline', \
              fontdict={'fontsize': '20',
                         'fontweight' : '3'})
    
    # position the annotation to the bottom left
    fig.annotate(start_date.strftime("%b, %Y"),
            xy=(-70, 22),
            horizontalalignment='right', verticalalignment='bottom',
            fontsize=14)
    
    # this will save the figure as a high-res png in the output path. you can also save as svg if you prefer.
    filepath = os.path.join(output_path, str(start_date)+'_.png')
    chart = fig.get_figure()
    chart.savefig(filepath, dpi=150)
    plt.close(chart)
    start_date += delta

### The following code uses imagemagik to convert the ficures into an animated gif and conver the gif into a smaller .mp4
### Run within directory containing plots
# convert -delay 5 -loop 1 202*.png stateMobility.gif
# ffmpeg -i stateMobility.gif -movflags faststart -pix_fmt yuv420p -vf "scale=trunc(iw/2)*2:trunc(ih/2)*2" stateMobility.mp4