#!/usr/bin/env python
import json
import argparse

latencys = [ 
	{ 'osd':[
		'op_latency',
		'op_process_latency',
		'op_r_latency',
		'op_r_process_latency',
		'op_w_rlat',
		'op_w_latency',
		'op_w_process_latency',
		'op_rw_rlat',
		'op_rw_process_latency',
		'subop_latency',
		'subop_w_latency',
		'subop_pull_latency',
		'subop_push_latency',
		]
	},

	{ 'filestore':[
		'journal_latency',
		'commitcycle_latency',
		'apply_latency',
		'queue_transaction_latency_avg',
		]
	}
]

def format_data(item, sum, avgcount):
    try:
        result = sum / avgcount * 1000
    except ZeroDivisionError:
        result = 0
    formatdata = '%-30s | %-30f | %-30f | %-30f' %(item, sum, avgcount, result )
    return formatdata

def handle_data(latencys):
    output = ['%-30s | %-30s | %-30s | %-30s' %('', 'sum', 'avgcount', 'latency/op (ms)')]
    for i in latencys:
        for component,items in i.items():   
            for item in items:
                sum = data[component][item]['sum']
                avgcount = data[component][item]['avgcount']
                result = format_data(item, sum, avgcount)
                output.append(result)
    return output
    
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--file', help='the full path of json file')
    args = parser.parse_args()

    f = open(args.file)
    data = json.load(f)
    output = handle_data(latencys)
    for i in  output:
        print i
