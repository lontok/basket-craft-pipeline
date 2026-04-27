select
    website_session_id,
    user_id,
    is_repeat_session::boolean as is_repeat_session,
    utm_source,
    utm_campaign,
    utm_content,
    device_type,
    http_referer,
    created_at
from {{ source('raw', 'website_sessions') }}
