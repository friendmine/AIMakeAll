// Both guest TCP paths use the same framed request and transmit all 256 results.
package main

import (
	"bufio"
	"bytes"
	"encoding/binary"
	"encoding/json"
	"io"
	"net"
	"os/exec"
	"time"
)

func serve(ln net.Listener, submit func(int, []byte) timing) int {
	conn, e := ln.Accept()
	check(e)
	defer conn.Close()
	reader := bufio.NewReader(conn)
	count := 0
	for {
		var id uint32
		e = binary.Read(reader, order, &id)
		if e == io.EOF {
			return count
		}
		check(e)
		var a [32]byte
		_, e = io.ReadFull(reader, a[:])
		check(e)
		r := submit(int(id), a[:])
		check(json.NewEncoder(conn).Encode(r))
		count++
	}
}
func call(link net.Conn, decoder *json.Decoder, id int, a []byte) timing {
	check(link.SetDeadline(time.Now().Add(3 * time.Second)))
	var frame [36]byte
	order.PutUint32(frame[:4], uint32(id))
	copy(frame[4:], a)
	_, e := link.Write(frame[:])
	check(e)
	var r timing
	check(decoder.Decode(&r))
	return r
}
func configurePeer(address string) {
	for _, args := range [][]string{{"modprobe", "e1000"}, {"ip", "link", "set", "eth0", "up"}, {"ip", "addr", "add", address, "dev", "eth0"}} {
		msg, e := exec.Command("/bin/busybox", args...).CombinedOutput()
		if e != nil {
			panic(string(msg) + e.Error())
		}
	}
}
func remoteClient(a, want []byte, digest string) map[string]any {
	var link net.Conn
	end := time.Now().Add(12 * time.Second)
	for time.Now().Before(end) {
		var e error
		link, e = net.DialTimeout("tcp4", "192.0.2.1:2022", time.Second)
		if e == nil {
			break
		}
		time.Sleep(100 * time.Millisecond)
	}
	require(link != nil, "peer connection timeout")
	defer link.Close()
	decoder := json.NewDecoder(link)
	rows := []timing{}
	for i := 0; i < 12; i++ {
		start := time.Now()
		r := call(link, decoder, i, a)
		r.ClientNS = time.Since(start).Nanoseconds()
		require(r.ID == i && r.Commands == 64 && r.Digest == digest && bytes.Equal(want, r.Results), "remote output mismatch")
		r.Results = nil
		rows = append(rows, r)
	}
	return map[string]any{"expected_sha256": digest, "rows": rows}
}
