import os
import pandas	as pd
from dotenv import load_dotenv
from helper import *
from tqdm import tqdm

load_dotenv()
token = os.environ['PAT']
enterprise_slug = os.environ['ENTERPRISE']
_is_enterprise_level = True

# Get activity summary and merge with enterprise_copilot_usage
print("Getting audit logs")
log = get_audit_log(enterprise_slug, token)
print("Processing audit logs")
github_audit_log = get_activity_summary(log, is_enterprise_level=_is_enterprise_level)
 
enterprise_copilot_usage = pd.DataFrame()
org_list = get_organizations(enterprise_slug, token)
for org in tqdm(org_list, desc="Processing organizations"):
	try:
		copilot_usage = get_copilot_usage(org, token)
		enterprise_copilot_usage = pd.concat([enterprise_copilot_usage, copilot_usage])
	except Exception as e:
		print(e)

copilot_activation_trend = pd.merge(github_audit_log, enterprise_copilot_usage, how='left', left_on=['Actor'], right_on=['assignee.login'])

#write it as output.md
with open('summary.md', 'w') as f:
	f.write(format_output(copilot_activation_trend))
