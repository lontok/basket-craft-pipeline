select
    website_pageview_id,
    website_session_id,
    pageview_url,
    created_at
from {{ source('raw', 'website_pageviews') }}
