import pandas as pd
import requests
import json
import os
import re
from keys import *

cityname = '香港特别行政区'

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
    folder_path = 'tmp/{}/'.format(cityname)
    if not os.path.exists(folder_path) :
        os.makedirs(folder_path)
    
    url = 'https://restapi.amap.com/v3/config/district?key={}&keywords={}&extensions=all'.format(key1, cityname)
    rt = query(url)

    data = {'city':[cityname], 'center':rt['districts'][0]['center'], 'polyline':[rt['districts'][0]['polyline']]}
    save('tmp/{}/district.csv'.format(cityname), data)

def stage1():
    def generate_url(x,y,i) :
        x = x / 10
        y = y / 10
        return 'https://restapi.amap.com/v3/place/polygon?polygon={:.6f},{:.6f}|{:.6f},{:.6f}&key={}&output=json&types=150500|150600|150700&city={}&citylimit=true&offset=25&page={}'.format(x,y,x+0.1,y+0.1, key1, cityname, i)

    border = load('tmp/{}/district.csv'.format(cityname))
    border = border['polyline'][0].split('|')
    border = sum([decode_polyline(s) for s in border], [])
    
    L = min(p[0] for p in border)
    R = max(p[0] for p in border)
    U = min(p[1] for p in border)
    D = max(p[1] for p in border)
    print(L, R, U, D)

    titles = ['id', 'name', 'location', 'address', 'cityname']
    data = {d:[] for d in titles}

    for x in range(int(L*10)-1, int(R*10)+2) :
        for y in range(int(U*10)-1, int(D*10)+2) :
            for i in range(1,100) :
                url = generate_url(x, y, i)
                rt = query(url)

                print(url)
                # print(rt)

                if len(rt['pois']) == 0 :
                    break
                
                for info in rt['pois'] :
                    for d in titles :
                        data[d].append(info.get(d, ''))
    
    save('tmp/{}/stations_in_rect.csv'.format(cityname), data)

def stage2():
    D = ['id', 'name', 'location', 'address', 'naddress', 'cityname', 'error']
    oD = ['id', 'name', 'location', 'address', 'cityname']

    ndata = {d:[] for d in D}
    
    data = load('tmp/{}/stations_in_rect.csv'.format(cityname)).to_dict(orient='list')
    n = len(data['name'])
    print(n)

    for i in range(n) :
        if data['cityname'][i] != cityname : continue

        url = 'https://restapi.amap.com/v3/assistant/inputtips?key={}&keywords={}&output=json&city={}&citylimit=true&location={}'.format(key1, data['name'][i], data['cityname'][i], data['location'][i])

        while True :
            flag = True
            try :
                r = requests.get(url).text
                rt = json.loads(r)
            except :
                flag = False
            if flag : break

        print('{} / {}'.format(i,n))
        print(url)
        # print(rt)
        print()

        for d in oD :
            ndata[d].append(data[d][i])

        find = False

        if 'tips' not in rt : continue

        for tips in rt['tips'] :
            # print(tips['id'], data['id'][i])
            # print(tips['name'], data['name'][i])

            if (tips['id'] == data['id'][i] and tips['name'] == data['name'][i]) :    
                find = True
                ndata['naddress'].append(tips['address'])
                ndata['error'].append(0)
                break
        
        if not find :
            ndata['naddress'].append(data['address'][i])
            ndata['error'].append(1)
    
    save('tmp/{}/stations_with_detail.csv'.format(cityname), ndata)

def stage3() :
    data = load('tmp/{}/stations_with_detail.csv'.format(cityname)).to_dict(orient='list')
    n = len(data['name'])
    print(n)

    bus = []

    for i in range(n) :
        if data['error'][i] == 1 :
            continue

        if (pd.isnull(data['naddress'][i])) :
            continue

        a = data['naddress'][i].split(';')
        for b in a :
            p = (data['cityname'][i], b.replace('(停运)','').replace('(在建)',''))
            if p not in bus :
                bus.append(p)
    
    D = ['id', 'type', 'status', 'name', 'polyline', 'citycode', 'busstops']
    ndata = {d:[] for d in D}

    for (c,b) in bus :
        url = 'https://restapi.amap.com/v3/bus/linename?s=rsv3&extensions=all&key={}&output=json&city={}&citylimit=false&keywords={}&platform=JS'.format(key2,c,b)
        r = requests.get(url).text
        rt = json.loads(r)

        print(url)
        # print(rt)

        try:
            print('search: ' + c + ' ' + b)
            for line in rt['buslines'] :
                if line['name'] not in ndata['name'] :
                    print(line['name'])

                    for d in D :
                        ndata[d].append(line[d])
            print()
        
        except:
            pass

    save('tmp/{}/bus.csv'.format(cityname), ndata)

def stage4() :
    def getstatus(id) :
        if id == 0 :
            return '停运'
        elif id == 1 :
            return '运行'
        elif id == 3 :
            return '在建'

    df = load('tmp/{}/bus.csv'.format(cityname))
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

    with open('data/{}.json'.format(cityname), mode='w') as f :
        json.dump(output, f)

if __name__ == '__main__' :
    # stage0()
    # stage1()
    # stage2()
    stage3()
    stage4()
    pass