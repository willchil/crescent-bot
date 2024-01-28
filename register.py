import httpx
from utility import get_headers


async def get_account(username, token) -> (bool, str):
    account_endpoint = f"https://accounts.rec.net/account?username={username}"

    async with httpx.AsyncClient() as client:
        response = await client.get(account_endpoint, headers=get_headers(token))

    # Check if the request was successful (status code 2xx)
    success = response.status_code // 100 == 2
    return (success, response.json())