# CRM Campaign Analysis

This module adds a custom report under CRM > Reporting titled 'Campaign Analysis'.

## Features

- Analyzes how leads tied to each campaign are distributed across stages over a date range
- Only includes leads where the campaign field is not null
- Groups leads by campaign and shows percentage distribution across all available stages
- Allows filtering based on lead creation date range

## Technical Details

- Accessible from menu: CRM > Reporting > Campaign Analysis
- Provides date range filter at the top
- Shows a table view with campaigns as rows and stages as columns
- Cell values show the percentage of leads in that stage for each campaign
- Uses SQL query for optimal performance
