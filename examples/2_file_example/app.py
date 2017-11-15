import asyncio
from gino import Gino, enable_task_local
from database import db, User


async def main():
    await db.create_pool('postgres://postgres@localhost/mydb')

    # Create object, `id` is assigned by database
    u1 = await User.create(user='fantix', age=10, message='test')
    print(u1.id, u1.user, u1.age, u1.message)  # 1 fantix 10 test
    
    
loop = asyncio.get_event_loop()
enable_task_local(loop)
loop.run_until_complete(main())
