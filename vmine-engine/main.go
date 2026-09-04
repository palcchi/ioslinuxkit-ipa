package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"log/slog"
	"os"
	"sort"
	"strings"

	"github.com/df-mc/dragonfly/server"
	"github.com/df-mc/dragonfly/server/player/chat"
	"github.com/pelletier/go-toml"
)

const operatorsFile = "operators.json"

func main() {
	slog.SetLogLoggerLevel(slog.LevelInfo)
	chat.Global.Subscribe(chat.StdoutSubscriber{})
	conf, err := readConfig(slog.Default())
	if err != nil {
		fmt.Println("VMINE_SERVER_ERROR:", err)
		os.Exit(1)
	}

	srv := conf.New()
	if err := srv.Listen(); err != nil {
		fmt.Println("VMINE_SERVER_ERROR:", err)
		os.Exit(1)
	}
	fmt.Println("VMINE_SERVER_READY:19132")
	go console(srv)
	for p := range srv.Accept() {
		_ = p
	}
	fmt.Println("VMINE_SERVER_CLOSED")
}

func console(srv *server.Server) {
	scanner := bufio.NewScanner(os.Stdin)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		line = strings.TrimPrefix(line, "/")
		if line == "" {
			continue
		}
		parts := strings.Fields(line)
		cmd := strings.ToLower(parts[0])
		args := parts[1:]
		switch cmd {
		case "help", "?":
			fmt.Println("Commands: help, stop, list, say <message>, kick <player> [reason], op <player>, deop <player>")
		case "stop":
			fmt.Println("Saving world and stopping server...")
			if err := srv.Close(); err != nil {
				fmt.Println("Stop error:", err)
			}
			return
		case "list":
			names := playerNames(srv)
			fmt.Printf("Players online (%d): %s\n", len(names), strings.Join(names, ", "))
			data, _ := json.Marshal(names)
			fmt.Printf("VMINE_PLAYERS:%s\n", data)
		case "say":
			if len(args) == 0 {
				fmt.Println("Usage: say <message>")
				continue
			}
			message := "[Server] " + strings.Join(args, " ")
			_, _ = chat.Global.WriteString(message)
			fmt.Println(message)
		case "kick":
			if len(args) == 0 {
				fmt.Println("Usage: kick <player> [reason]")
				continue
			}
			reason := "Kicked by server operator."
			if len(args) > 1 {
				reason = strings.Join(args[1:], " ")
			}
			if !kickPlayer(srv, args[0], reason) {
				fmt.Println("Player not found:", args[0])
			}
		case "op", "deop":
			if len(args) != 1 {
				fmt.Printf("Usage: %s <player>\n", cmd)
				continue
			}
			ops, _ := loadOperators()
			key := strings.ToLower(args[0])
			if cmd == "op" {
				ops[key] = args[0]
				fmt.Println("Operator added:", args[0])
			} else {
				delete(ops, key)
				fmt.Println("Operator removed:", args[0])
			}
			if err := saveOperators(ops); err != nil {
				fmt.Println("Operator save error:", err)
			}
		default:
			fmt.Printf("Unknown command: %s. Type help for available commands.\n", cmd)
		}
	}
}

func playerNames(srv *server.Server) []string {
	var names []string
	for p := range srv.Players(nil) {
		names = append(names, p.Name())
	}
	sort.Strings(names)
	return names
}

func kickPlayer(srv *server.Server, name, reason string) bool {
	for p := range srv.Players(nil) {
		if strings.EqualFold(p.Name(), name) {
			p.Disconnect(reason)
			fmt.Println("Kicked:", p.Name())
			return true
		}
	}
	return false
}

func loadOperators() (map[string]string, error) {
	ops := map[string]string{}
	data, err := os.ReadFile(operatorsFile)
	if os.IsNotExist(err) {
		return ops, nil
	}
	if err != nil {
		return ops, err
	}
	return ops, json.Unmarshal(data, &ops)
}

func saveOperators(ops map[string]string) error {
	data, err := json.MarshalIndent(ops, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(operatorsFile, data, 0644)
}

func readConfig(log *slog.Logger) (server.Config, error) {
	c := server.DefaultConfig()
	var zero server.Config
	if _, err := os.Stat("config.toml"); os.IsNotExist(err) {
		data, err := toml.Marshal(c)
		if err != nil { return zero, fmt.Errorf("encode default config: %v", err) }
		if err := os.WriteFile("config.toml", data, 0644); err != nil { return zero, fmt.Errorf("create default config: %v", err) }
		return c.Config(log)
	}
	data, err := os.ReadFile("config.toml")
	if err != nil { return zero, fmt.Errorf("read config: %v", err) }
	if err := toml.Unmarshal(data, &c); err != nil { return zero, fmt.Errorf("decode config: %v", err) }
	return c.Config(log)
}
