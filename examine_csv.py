import csv
import sys

try:
    with open('deepsearch_complete.csv', 'r', encoding='utf-8', errors='ignore') as f:
        reader = csv.reader(f)
        headers = next(reader)
        print('Headers:', headers)
        print('Number of headers:', len(headers))
        print('\nFirst 3 rows:')
        for i, row in enumerate(reader):
            if i < 3:
                print(f'Row {i}: {row[:5]}...')  # Show first 5 columns
except Exception as e:
    print(f'Error: {e}')
