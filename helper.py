import json
import requests
import pandas as pd
from datetime import datetime, timedelta

class CopilotHelper:
    """
    A helper class for retrieving and summarizing GitHub Copilot usage and audit logs.
    """
    def __init__(self, token):
        self.token = token
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28"
        }

    def get_audit_log(self, slug_name: str, is_enterprise: bool):
        """
        Retrieves the audit log for a given slug name and organization type.

        Args:
          slug_name (str): The name of the slug (organization or enterprise).
          is_enterprise (bool): Indicates whether the slug is an enterprise or organization.

        Returns:
          list: A list of audit log entries.

        Raises:
          Exception: If the audit log retrieval fails.
        """
        slug_type = "enterprises" if is_enterprise else "orgs"
        url = f"https://api.github.com/{slug_type}/{slug_name}/audit-log?phrase=action:pull_request&per_page=100&page=1"

        # Get the next page if it exists
        logs = []
        while True:
            # Get the audit log
            log_page = requests.get(url, headers=self.headers)
            logs.extend(log_page.json())
    
            # If the status code is 403, raise an exception
            if log_page.status_code != 200:
                raise Exception(f"Failed to fetch audit log. Status code: {log_page.status_code}")
    
            # If there is no next page, break the loop
            if 'Link' not in log_page.headers:
                break
    
            # Get the next page
            links = {}
            for head in log_page.headers['Link'].split(','):
                url, rel = head.split(';')
                rel = rel.split('=')[1].replace('"', '')
                url = url.replace('<', '').replace('>', '')
                links[rel] = url
    
            # If there is no next page, break the loop
            if 'next' not in links:
                break
            url = links['next']
    
        return logs
    
    def get_copilot_usage(self, org_name: str):
        """
        Retrieves the usage data for GitHub Copilot in the specified organization.

        Args:
          org_name (str): The name of the organization.

        Returns:
          pandas.DataFrame: A DataFrame containing the Copilot usage data, including the assignee's login, activation date, last activity date, last activity editor, and Copilot organization name.
        """
        url = f"https://api.github.com/orgs/{org_name}/copilot/billing/seats"
        usage = requests.get(url, headers=self.headers).json()
    
        if 'seats' not in usage:
            return pd.DataFrame()
        usage = pd.json_normalize(usage, record_path=['seats'])[['assignee.login', 'created_at', 'last_activity_at', 'last_activity_editor']]
        usage['org_name'] = org_name
    
        # Rename the headers and convert the date columns to datetime
        usage.rename(columns={'created_at': 'Activation', 'last_activity_at': 'Last Activity', 'last_activity_editor': 'Last Activity Editor', 'org_name': 'Copilot Organization'}, inplace=True)
        usage['Activation'] = pd.to_datetime(usage['Activation']).dt.date
        usage['Last Activity'] = pd.to_datetime(usage['Last Activity']).dt.date
    
        return usage
    
    def get_organizations(self, enterprise_slug: str):
        """
        Retrieves a list of organization names associated with the given enterprise slug.

        Args:
          enterprise_slug (str): The slug of the enterprise.

        Returns:
          list: A list of organization names.
        """
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
        organizations = requests.post(url, headers=self.headers, json={'query': query, 'variables': variables}).json()
    
        if 'errors' in organizations:
            print(organizations['errors'][0]['message'])
    
        return [org['name'] for org in organizations['data']['enterprise']['organizations']['nodes'] if org is not None]
    
    def summarize_logs(self, logs: list):
        """
        Summarizes the logs by performing various data transformations and aggregations.

        Args:
          logs (list): A list of log entries.

        Returns:
          pandas.DataFrame: A DataFrame containing the summarized log data.
        """
        # Normalize the logs
        df = pd.json_normalize(logs)
        df.drop(columns=['business'], inplace=True)
        df.rename(columns={'org': 'Organization', 'actor': 'Actor'}, inplace=True)
    
        # Get the action type
        df['action_type'] = df['action'].apply(lambda x: x.split('.')[0])
    
        # If Actor = Organization, then delete the row. This is assumed to be a bot
        df = df[df['Actor'] != df['Organization']]
    
        # Group and pivot the data
        grouped_df = df.groupby(['Organization', 'Actor', 'action_type']).size().reset_index(name='operation count')
        pivoted_df = pd.pivot_table(grouped_df, index=['Organization', 'Actor'], columns='action_type', values='operation count', fill_value=0, aggfunc='sum').reset_index()
        pivoted_df.rename(columns={'pull_request': 'Pull Request' }, inplace=True)
    
        # Select the keys and group by Actor
        keys = [key for key in ['Organization', 'Actor', 'Pull Request'] if key in pivoted_df.columns]
        pivoted_df = pivoted_df[keys].groupby(['Actor']).sum().reset_index().sort_values(['Pull Request'], ascending=False)
    
        return pivoted_df
    
    
    def format_output(self, data, template_file):
        """
        Formats the given data into a markdown table.

        Args:
          data (pandas.DataFrame): The data to be formatted.
          template_file (str): The path to the template file.

        Returns:
          str: The formatted markdown table.
        """
        # Read the md from ./template.md
        if template_file == "potential-report-template.md":
            with open(template_file, 'r') as file:
                markdown = file.read()
                for index, row in data.fillna("").iterrows():
                    if row['Actor'] in ["github-actions[bot]", "dependabot[bot]"]:
                        continue
                    markdown += (f"| {row['Actor']} | {row['Copilot Organization']} | {row['Pull Request']} | {row['Activation']} | {row['Last Activity']} | {row['Last Activity Editor']} |\n")
        elif template_file == "usage-report-template.md":
            with open(template_file, 'r') as file:
                markdown = file.read()
                for index, row in data.fillna("").iterrows():
                    markdown += (f"| {row['assignee.login']} | {row['Copilot Organization']} | {row['Activation']} | {row['Last Activity']} | {row['Last Activity Editor']} |\n")
        else:
            markdown = "Invalid template file"
    
        return markdown
    