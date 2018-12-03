import asyncio
import json

import motor.motor_asyncio
import redis


async def migrate_cc(rdb, mdb):
    print("Migrating CCs...")
    old_ccs = json.loads(rdb.get('commands.json'))
    for server, ccs in old_ccs.items():
        print(f"Migrating server {server}...")
        commands = []
        for cmd, responses in ccs.items():
            print(f"Migrating {cmd}...")
            commands.append({"name": cmd.strip(), "responses": responses})
        new_cc = {
            "server": server,
            "commands": commands
        }
        await mdb.custcommands.insert_one(new_cc)
        print(f"Migrated {len(commands)} commands.")
    await mdb.custcommands.create_index("server")


async def migrate_join(rdb, mdb):
    print("Migrating join...")
    old = json.loads(rdb.get('ja-settings'))
    for server, settings in old.items():
        print(f"Migrating {server}...")
        new = {
            "server": server,
            "messages": settings['messages'],
            "destination": settings.get('destination'),
            "enabled": settings.get('enabled'),
            "deleteafter": 0
        }
        await mdb.join.insert_one(new)
    await mdb.join.create_index("server")


async def migrate_mod(rdb, mdb):
    print("Migrating mod...")
    case_nums = json.loads(rdb.get('case_nums'))
    force_bans = json.loads(rdb.get('force_ban'))
    mod_log = json.loads(rdb.get('mod_log'))

    for server, cases in mod_log.items():
        print(f"Migrating {server}...")
        new_cases = []
        for case in cases:
            new_case = {
                "num": case['id'],
                "type": case['type'],
                "user": case['user'],
                "reason": None,
                "mod": None,
                "log_msg": case['msg'],
                "username": case['user_name']
            }
            new_cases.append(new_case)

        casenum = case_nums.get(server, 0)
        forcebanned = force_bans.get(server, [])

        new = {
            "server": server,
            "raidmode": None,
            "cases": new_cases,
            "casenum": casenum,
            "forcebanned": forcebanned,
            "locked_channels": []
        }
        await mdb.mod.insert_one(new)

    await mdb.mod.create_index("server")


async def run(rdb, mdb):
    await migrate_cc(rdb, mdb)
    await migrate_join(rdb, mdb)
    await migrate_mod(rdb, mdb)


if __name__ == '__main__':
    mdb = motor.motor_asyncio.AsyncIOMotorClient(input("Mongo: ")).azuth
    rdb = redis.from_url(input("Redis: "))
    asyncio.get_event_loop().run_until_complete(run(rdb, mdb))
