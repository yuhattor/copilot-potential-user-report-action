import os
import pandas as pd
from dotenv import load_dotenv
from tqdm import tqdm

from helper import *

load_dotenv()
token = os.environ['PAT']
slug_name = os.environ['SLUGNAME']
slug_type = os.environ['SLUGTYPE']
audit_log = os.environ.get('AUDITLOG', 'true')

ch = CopilotHelper(token)

if slug_type == "enterprise":
    # Get the copilot usage for each organization and concatenate the dataframes
    enterprise_copilot_usage = pd.DataFrame()
    organizations = ch.get_organizations(slug_name)
    for organization in tqdm(organizations, desc="Processing organizations"):
        try:
            organization_copilot_usage = ch.get_copilot_usage(organization)
            enterprise_copilot_usage = pd.concat([enterprise_copilot_usage, organization_copilot_usage])
        except Exception as e:
            print(e)
else:
    # Get the copilot usage for the organization
    enterprise_copilot_usage = ch.get_copilot_usage(slug_name)

with open('summary.md', 'w') as f:
    if not enterprise_copilot_usage.empty:
        if audit_log == 'true':
            logs = ch.get_audit_log(slug_name, (slug_type == "enterprise"))
            audit_logs = ch.summarize_logs(logs)
            copilot_activation_trend = pd.merge(audit_logs, enterprise_copilot_usage, how='left', left_on=['Actor'], right_on=['assignee.login'])
            f.write(ch.format_output(copilot_activation_trend, "potential-report-template.md"))
        else:
            f.write(ch.format_output(enterprise_copilot_usage, "usage-report-template.md"))
    else:
        f.write("# No Copilot usage found\n")
