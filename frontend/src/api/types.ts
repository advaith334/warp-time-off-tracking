import type { components } from './schema'

type ApiSchemas = components['schemas']

// Ergonomic names for the generated OpenAPI response types used by the UI.
export type Employee = ApiSchemas['EmployeeOut']
export type Category = ApiSchemas['CategoryOut']
export type Rule = ApiSchemas['AccrualRuleOut']
export type PolicyVersion = ApiSchemas['PolicyVersionOut']
export type Policy = ApiSchemas['PolicyOut']
export type Holiday = ApiSchemas['HolidayOut']
export type Balance = ApiSchemas['BalanceOut']
export type LedgerEntry = ApiSchemas['LedgerEntryOut']
export type JobRun = ApiSchemas['JobRunOut']
export type TimeOffRequest = ApiSchemas['TimeOffRequestOut']
