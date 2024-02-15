import pandas as pd
import requests
import json
import os
import re
import time
from keys import *

# cityname, citycode, cityname_8684 = '广州市', '020', 'guangzhou'
# cityname, citycode, cityname_8684 = '武汉市', '027', 'wuhan'
cityname, citycode, cityname_8684 = '南京市', '025', 'nanjing'

def query(url) :
    r = requests.get(url).text
    return json.loads(r)

def load(filename) :
    return pd.read_csv(filename)
    
def save(filename, data) :
    df = pd.DataFrame(data)
    df.to_csv(filename, encoding='utf-8-sig', index=None)

def decode_polyline(line) :
    line = [s.split(',') for s in line.split(';')]
    return [[float(p[0]), float(p[1])] for p in line]

def stage0() :
    workdir= 'tmp/{}/'.format(cityname)
    if not os.path.exists(workdir) :
        os.makedirs(workdir)
    
    url = 'https://restapi.amap.com/v3/config/district?key={}&keywords={}&extensions=all'.format(key, cityname)
    rt = query(url)

    data = {'city':[cityname], 'center':rt['districts'][0]['center'], 'polyline':[rt['districts'][0]['polyline']]}
    save('tmp/{}/district.csv'.format(cityname), data)


def stage1() :
    list1 = [chr(x) for x in range(ord('A'), ord('Z') + 1)] + \
             [str(y) for y in range(10)]
    bus = []
    
    for i in list1 :
        url = 'https://{}.8684.cn/list{}'.format(cityname_8684, i)
        r = requests.get(url)
        r.status_code
        r = r.text
        
        r = r[r.find('"list clearfix">')+len('"list clearfix">'):]
        r = r[:r.find('</div>')]
        r = list(filter(lambda s : len(s)>0, map(lambda s : s[s.find('>')+1:], r.split('</a>'))))
        bus += r
    
    ndata = {'name':bus}
    save('tmp/{}/bus_name_8684.csv'.format(cityname), ndata)

def stage2(reset=False, start=None) :
    Db = ['id', 'type', 'status', 'name', 'polyline', 'citycode', 'busstops']
    Ds = ['id', 'name', 'citycode', 'buslines']
    Dq = ['type', 'id']

    workdir = 'tmp/{}/'.format(cityname)
    if not os.path.exists(workdir):
        os.makedirs(workdir)
    
    buslines = {d:[] for d in Db}
    busstops = {d:[] for d in Ds}
    queue = {d:[] for d in Dq}

    if not reset :
        if os.access('tmp/{}/buslines.csv'.format(cityname), os.F_OK) :
            buslines = load('tmp/{}/buslines.csv'.format(cityname)).to_dict(orient='list')
        if os.access('tmp/{}/busstops.csv'.format(cityname), os.F_OK) :
            busstops = load('tmp/{}/busstops.csv'.format(cityname)).to_dict(orient='list')
        if os.access('tmp/{}/queue.csv'.format(cityname), os.F_OK) :
            queue = load('tmp/{}/queue.csv'.format(cityname)).to_dict(orient='list')

    if start != None :
        queue['type'].append(start[0])
        queue['id'].append(start[1])

    cb, cs = 0, 0

    def saveall() :
        save('tmp/{}/buslines.csv'.format(cityname), buslines)
        save('tmp/{}/busstops.csv'.format(cityname), busstops)
        save('tmp/{}/queue.csv'.format(cityname), queue)

    while queue['type'] != [] :
        type = queue['type'][0]
        id = queue['id'][0]

        if type == 'b' and id not in buslines['id'] :
            url = 'https://restapi.amap.com/v3/bus/lineid?key={}&id={}&extensions=all'.format(key, id)
        elif type == 's' and id not in busstops['id'] :
            url = 'https://restapi.amap.com/v3/bus/stopid?key={}&id={}'.format(key, id)
        
        print(url)
        r = requests.get(url).text
        rt = json.loads(r)
        # print(rt)

        if rt['status'] == '0' :
            saveall()
            raise RuntimeError(r)

        if type == 'b' :
            cb += 1
            for line in rt['buslines'] :
            
                print(line['name'])
                
                for d in Db :
                    buslines[d].append(line[d])
                
                for s in line['busstops'] :
                    if s['id'] not in busstops['id'] and s['id'] not in queue['id'] :
                        queue['type'].append('s')
                        queue['id'].append(s['id'])

        elif type == 's' :
            cs += 1
            for stop in rt['busstops'] :
                print(stop['name'])
                
                if stop['citycode'] == citycode :
                    for d in Ds :
                        busstops[d].append(stop[d])
                
                    for b in stop['buslines'] :
                        if b['id'] not in buslines['id'] and b['id'] not in queue['id'] :
                            queue['type'].append('b')
                            queue['id'].append(b['id'])

        queue['type'] = queue['type'][1:]
        queue['id'] = queue['id'][1:]

        if (cb + cs) % 100 == 0 :
            saveall()
    
    saveall()

        

def stage3() :
    def getstatus(id) :
        if id == 0 :
            return '停运'
        elif id == 1 :
            return '运行'
        elif id == 3 :
            return '在建'

    df = load('tmp/{}/buslines.csv'.format(cityname))
    n = len(df['name'])

    lineinfo = []
    for i in range(n) :
        path = decode_polyline(df['polyline'][i])
        bus = {"name" : df['name'][i], "type" : df['type'][i], "status" : getstatus(df['status'][i]), "path" : path}
        lineinfo.append(bus)

    district = load('tmp/{}/district.csv'.format(cityname))
    border = district['polyline'][0].split('|')
    border = [decode_polyline(s) for s in border]
    center = [float(x) for x in district['center'][0].split(',')]

    output = {"center" : center, "city_polyline" : border, "lineInfo" : lineinfo}

    workdir = 'data/'.format(cityname)
    if not os.path.exists(workdir):
        os.makedirs(workdir)
    with open('data/{}.json'.format(cityname), mode='w') as f :
        json.dump(output, f)

if __name__ == '__main__' :
    # stage0()
    # stage1() 
    # stage2(start=('b','900000089758'))
    stage3()
    pass