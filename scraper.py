import re
import unicodedata
import pandas as pd
import requests as r
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

def scrape_text_from_link(link):
    response = r.get(link)
    return BeautifulSoup(response.text)

def create_tables_from_page_html(tourney_results_html, tourney_id):
    tanks_df = pd.DataFrame()
    info_df = pd.DataFrame()
    for t in tourney_results_html.find_all('div', class_ = 'tournylist'):
        # tourney tanks
        for row in t.find_all('tr', class_ = 'tourny-placing'):
            row_dict = {}
            count = 0
            for col in row.find_all('td'):
                row_dict[ 'tourney_id'] = tourney_id
                if col.find_all(class_ = 'tank-link'):
                    row_dict[ 'tank_id' ] = re.sub('\\"\\>.+', '', re.sub('.+tank_id=', '', re.sub('\\s+', '', str(col))))
                    row_dict[ 'tank_name' ] = col.get_text().strip()
                elif col.find_all(class_ = 'awards-sprite'):
                    row_dict[ 'awards_raw' ] = str(col)
                else:
                    row_dict[ count ] = col.get_text()
                    count += 1
            tanks_df = pd.concat([tanks_df, pd.DataFrame([row_dict])], axis = 0)
        # tourney info
        for tourney_table in t.find_all('table', class_ = 'tournament-results'):
            tourney_table_first_row = tourney_table.find_all('tr')[0]
            col_list = []
            col_list.append(tourney_id)
            for tourney_table_first_row_line in tourney_table_first_row.get_text().split('\n'):
                tourney_table_first_row_line = unicodedata.normalize("NFKD", tourney_table_first_row_line)
                line_text = re.sub('\\s+', ' ', tourney_table_first_row_line)
                line_text = line_text.strip()
                if line_text != '':
                    col_list.append(line_text)
            info_df = pd.concat([info_df, pd.DataFrame([col_list])], axis = 0)
    return tanks_df, info_df

def get_diff_btwn_time_strings(time_strings, time_format):
    time_1_string = time_strings[0]
    time_2_string = time_strings[1]
    time_1 = datetime.strptime(time_1_string, time_format)
    time_2 = datetime.strptime(time_2_string, time_format)
    time_diff = time_2 - time_1
    if time_diff < timedelta(hours = 0):
        time_2 = time_2 + timedelta(hours = 24)
        time_diff = time_2 - time_1
    return time_diff

def transform_tourney_info_df(info_df):
    info_df['start_string'], info_df['end_string'] = info_df['time'].str.split('-').str
    # structure tourney start time as datetime
    info_df['start_time'] = info_df['date'] + ' ' + info_df['start_string']
    info_df['start_time'] = pd.to_datetime(info_df['start_time'], format = '%B %d, %Y %H:%M')
    # convert from GMT to Eastern
    info_df['start_time'] = info_df['start_time'] - timedelta(hours = 4)
    # get tourney duration
    info_df['duration'] = info_df['time'].apply(lambda i: get_diff_btwn_time_strings(i.split('-'), '%H:%M'))
    info_df['duration'] = info_df['duration'].astype(int).astype(float) // 3600. // 100000000. / 10.
    # drop unnecessary cols
    info_df = info_df.drop('date', axis = 1)
    info_df = info_df.drop('time', axis = 1)
    info_df = info_df.drop('start_string', axis = 1)
    info_df = info_df.drop('end_string', axis = 1)
    return info_df

def loop_all_tourneys(tourney_id_list, no_param_url = 'https://tankpit.com/tournament_results/?tid='):
    master_tanks_df = pd.DataFrame()
    master_info_df = pd.DataFrame()
    for tourney_id in tourney_id_list:
        print tourney_id
        # scrape
        tourney_results_html = scrape_text_from_link(no_param_url + str(tourney_id))
        # make tables
        tanks_df, info_df = create_tables_from_page_html(tourney_results_html, tourney_id)
        # concat
        master_tanks_df = pd.concat([master_tanks_df, tanks_df], axis = 0)
        master_info_df = pd.concat([master_info_df, info_df], axis = 0)
    # rename cols
    master_tanks_df.rename(columns = {0: 'number', 1: 'color', 2: 'rank'}, inplace = True)
    if 3 in master_tanks_df.columns:
        master_tanks_df.drop(3, axis = 1, inplace = True)
    master_tanks_df.reset_index(drop = True, inplace = True)
    # tourney info
    master_info_df.rename(columns = {0: 'tourney_id', 1: 'map', 2: 'date', 3: 'time'}, inplace = True)
    master_info_df.reset_index(drop = True, inplace = True)
    return master_tanks_df, master_info_df

if __name__ == "__main__":
    # what's the current max tourney_id?
    max_tourney_id = 795
    # run the loop!
    master_tanks_df, master_info_df = loop_all_tourneys(tourney_id_list = range(max_tourney_id))
    master_info_df = transform_tourney_info_df(master_info_df)
    # removing awards for now
    master_tanks_df = master_tanks_df.drop('awards_raw', axis = 1)
    master_tanks_df.to_csv('./data/tourney_tanks.csv', sep = ',', header = True, index = False, quotechar = '"')
    master_info_df.to_csv('./data/tourney_info.csv', sep = ',', header = True, index = False, quotechar = '"')
