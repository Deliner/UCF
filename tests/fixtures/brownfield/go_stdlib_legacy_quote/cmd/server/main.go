package main

import (
	"context"
	"errors"
	"flag"
	"fmt"
	"log"
	"net"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"example.com/legacyquotes/quote"
)

func main() {
	log.SetFlags(0)
	listenAddress := flag.String(
		"listen",
		"127.0.0.1:8080",
		"TCP listen address",
	)
	flag.Parse()
	if flag.NArg() != 0 {
		log.Fatal("unexpected positional argument")
	}
	listener, err := net.Listen("tcp4", *listenAddress)
	if err != nil {
		log.Fatal(err)
	}
	server := &http.Server{
		Handler:           quote.Handler(),
		ReadHeaderTimeout: 2 * time.Second,
	}

	signalContext, stopSignals := signal.NotifyContext(
		context.Background(),
		os.Interrupt,
		syscall.SIGTERM,
	)
	defer stopSignals()
	shutdownResult := make(chan error, 1)
	go func() {
		<-signalContext.Done()
		shutdownContext, cancel := context.WithTimeout(
			context.Background(),
			2*time.Second,
		)
		defer cancel()
		shutdownResult <- server.Shutdown(shutdownContext)
	}()

	fmt.Printf("READY http://%s\n", listener.Addr())
	if err := server.Serve(listener); !errors.Is(err, http.ErrServerClosed) {
		log.Fatal(err)
	}
	if signalContext.Err() != nil {
		if err := <-shutdownResult; err != nil {
			log.Fatal(err)
		}
	}
}
