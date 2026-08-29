# V-MINE

V-MINE is the dedicated Bedrock server direction for this project.

The user-facing product is an iOS/iPadOS server manager, not a general Linux terminal. The existing Linux userspace kernel and direct x86_64 guest interpreter are implementation details used to run Mojang's official Linux Bedrock Dedicated Server binary on ARM64 iOS hardware.

## Product goal

V-MINE should let a user:

- install the current Bedrock Dedicated Server package from Mojang/Minecraft sources;
- start and stop the server from a native iOS interface;
- view and send console commands;
- configure `server.properties` without editing text files manually;
- manage, import, export and back up worlds;
- manage allowlist and permissions;
- show server version, port, player count and runtime status;
- check for a newer official server package and update without deleting user data.

## Runtime architecture

```text
iOS / iPadOS ARM64
        |
        v
V-MINE native host UI
        |
        v
direct x86_64 compatibility runtime
        |
        v
minimal Linux/glibc runtime
        |
        v
Mojang Bedrock Dedicated Server (x86_64 ELF)
```

The downloaded BDS executable is guest Linux code interpreted by the runtime. It is not executed as a native iOS Mach-O binary.

## Scope

Compatibility work is BDS-first. The project does not need to become a complete x86_64 Linux desktop environment. New instruction, syscall, filesystem, networking and signal support should be prioritized according to what the official BDS binary and its runtime actually use.

A compatibility milestone is complete only when BDS can:

1. start successfully;
2. create or load a world;
3. listen on the configured Bedrock UDP port;
4. accept a Bedrock client;
5. save world data correctly;
6. process console commands;
7. stop cleanly without corrupting the world.

## Server installation and updates

The app should not treat the BDS package as permanent application content. The server manager should maintain separate engine and user-data locations, conceptually:

```text
V-MINE/
  Runtime/
  Server/
  Data/
    worlds/
    server.properties
    permissions.json
    allowlist.json
  Backups/
```

Update flow:

1. determine the currently available official BDS version;
2. download the official Linux server archive from Minecraft/Mojang infrastructure;
3. verify the download before replacing the installed engine when verification information is available;
4. create a world/configuration backup;
5. stop the running server;
6. replace server engine files while preserving V-MINE user data;
7. restart only after installation succeeds.

An update failure must leave the previous working server and user data recoverable.

## Native UI direction

Primary sections:

- Home: server state, Start/Stop, version, address, port and player count.
- Console: live server output and command input.
- Worlds: world selection, import/export and backups.
- Players: connected players, allowlist and permissions.
- Settings: server name, game mode, difficulty, cheats, max players, port and other supported `server.properties` values.
- Updates: installed version, available version and update state.

The Linux terminal should not be the normal user experience. A developer console may remain available behind a development build or diagnostics screen.

## Data safety

World data is more important than the replaceable server engine. Before server updates and other destructive operations, V-MINE should create recoverable backups and use atomic/staged replacement where practical.

## Branding and provenance

Product name: **V-MINE**.

V-MINE is an independent project and is not affiliated with or endorsed by Mojang Studios or Microsoft. Minecraft and Bedrock are trademarks of their respective owners. The project retains the licences and attribution requirements of the ios-linuxkit/iSH-derived runtime and its dependencies.
