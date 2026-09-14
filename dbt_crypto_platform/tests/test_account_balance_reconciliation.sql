-- Singular test: account balance and locked_balance must be non-negative
select
    account_id,
    user_id,
    balance,
    locked_balance
from {{ ref('stg_postgres__accounts') }}
where balance < 0 or locked_balance < 0
