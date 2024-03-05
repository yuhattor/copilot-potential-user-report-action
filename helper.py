import json
import requests
import pandas as pd
from datetime import datetime, timedelta

def get_audit_log(enterprise_slug: "String of the enterprise slug", token: "String of the token"):
	date = (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d')
	url = f"https://api.github.com/enterprises/customer-success-architects-ea-sandbox/audit-log?phrase=action:pull_request+created:>={date}"
	headers = {
		"Accept": "application/vnd.github.v3+json",
		"Authorization": f"Bearer {token}"
	}
	result = requests.get(url, headers=headers)
	return result.json()

def get_activity_summary(data: "hashmap array of the audit log", is_enterprise_level: "True or False" = True) -> "Pandas DataFrame":
	df = pd.json_normalize(data)
	# Organize the data
	df.rename(columns={'business': 'Enterprise', 'org': 'Organization', 'actor': 'Actor'}, inplace=True)
	
	# If it's a git log, need more details on the action type
	df['action_type'] = df['action'].apply(lambda x: x.split('.')[0])
	keys = ['Enterprise', 'Organization', 'Actor', 'Pull Request', 'Pull Request Review', 'Issue Comment']

	# if Actor = Organization, then delete the row
	df = df[df['Actor'] != df['Organization']]

	# Group and pivot the data
	grouped_df = df.groupby(['Enterprise', 'Organization', 'Actor', 'action_type']).size().reset_index(name='operation count')
	pivoted_df = pd.pivot_table(grouped_df, index=['Enterprise', 'Organization', 'Actor'], columns='action_type', values='operation count', fill_value=0, aggfunc='sum').reset_index()

	# Select the keys
	pivoted_df.rename(columns={'pull_request': 'Pull Request', 'pull_request_review': 'Pull Request Review', 'issue_comment': 'Issue Comment', 'git.clone': 'Git Clone', 'git.fetch': 'Git Fetch', 'git.push': 'Git Push' }, inplace=True)
	keys = [key for key in keys if key in pivoted_df.columns]
	pivoted_df = pivoted_df[keys]

	if is_enterprise_level:
		pivoted_df.drop(columns=['Organization'], inplace=True)
		pivoted_df = pivoted_df.groupby(['Enterprise', 'Actor']).sum().reset_index()
	else:
		pivoted_df = pivoted_df.groupby(['Enterprise', 'Organization', 'Actor']).sum().reset_index()

	pivoted_df = pivoted_df.sort_values(['Pull Request'], ascending=False)

	return pivoted_df

def get_copilot_usage(org_name: "String of the organization name", token: "String of the token"):
	url = f"https://api.github.com/orgs/{org_name}/copilot/billing/seats"
	headers = {
		"Accept": "application/vnd.github+json",
		"Authorization": f"Bearer {token}",
		"X-GitHub-Api-Version": "2022-11-28"
	}
	result = requests.get(url, headers=headers)

	if 'seats' not in result.json():
		return pd.DataFrame()
	copilot_usage = pd.json_normalize(result.json(), record_path=['seats'])[['assignee.login', 'created_at', 'last_activity_at', 'last_activity_editor']]
	copilot_usage['org_name'] = org_name

	# Rename the headers and convert the date columns to datetime
	copilot_usage.rename(columns={'created_at': 'Activation', 'last_activity_at': 'Last Activity', 'last_activity_editor': 'Last Activity Editor', 'org_name': 'Copilot Organization'}, inplace=True)
	copilot_usage['Activation'] = pd.to_datetime(copilot_usage['Activation']).dt.date
	copilot_usage['Last Activity'] = pd.to_datetime(copilot_usage['Last Activity']).dt.date
	return copilot_usage

def get_organizations(enterprise_slug: "String of the enterprise slug", token: "String of the token"):
		url = 'https://api.github.com/graphql'
		query = """
		query($slug: String!) {
			enterprise(slug: $slug) {
				slug
				id
				organizations(first: 100) {
					nodes {
						name
					}
				}
			}
		}
		"""
		variables = {
			"slug": enterprise_slug
		}
		headers = {
				"Authorization": f"Bearer {token}",
				"Content-Type": "application/json"
		}
		response = requests.post(url, headers=headers, json={'query': query, 'variables': variables})
		org_list = response.json()['data']['enterprise']['organizations']['nodes']
		return [i['name'] for i in org_list if i is not None]

def format_output(data):
	markdown = f"""
# 🤖 Copilot usage trends against GitHub activity (PR)

This report is generated from the last 180 days of GitHub activity and Copilot usage. The report is generated from the audit log and Copilot billing API. The report is generated on {datetime.now().strftime('%Y-%m-%d')}
If there are members who create PRs but are not using Copilot, it is recommended to encourage them to use Copilot to improve their productivity 🚀

| Name | Copilot Organization | # of PR in 180 days | Activation | Last Activity | Last Activity Editor |
| --- | --- | --- | --- | --- | --- |
"""

	for index, row in data.iterrows():
		for column in data.columns:
			if pd.isna(row[column]):
				row[column] = ""

		if row['Actor'] == "dependabot[bot]":
			continue

		markdown += (f"| {row['Actor']} | {row['Copilot Organization']} | {row['Pull Request']} | {row['Activation']} | {row['Last Activity']} | {row['Last Activity Editor']} |\n")

	return markdown
