package schedule

import "time"

func Start(d time.Duration, f func()) {
	t := time.NewTicker(d)
	
	go func() {
		for range t.C {
			f()
		}
	}()
}
