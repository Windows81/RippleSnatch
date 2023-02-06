from collections import deque
import threading
import argparse
import typing
import grab
import save


def iterate(ids: list[int], th: int = 1) -> None:
    attrs = {
        "quit": False,
        "limit": 0,
        "threads": 0,
    }

    def print_progress(i: int, base_id: int, info: dict | None) -> None:
        if not info:
            return
        if attrs['quit']:
            print(f"{base_id} ({i}/{attrs['limit']} - {attrs['threads']})")
        else:
            print(base_id)

    def process(r: typing.Iterable[int]) -> typing.Generator[tuple[int, dict], None, None]:
        for i, base_id in enumerate(r):
            if i > attrs['limit']:
                if attrs['quit']:
                    break
                attrs['limit'] = i

            info = grab.try_entry(base_id)
            print_progress(i, base_id, info)
            yield (base_id, info)

    def thread_body(queue: deque[dict], gen: typing.Generator[tuple[int, dict], None, None]) -> None:
        attrs['threads'] += 1
        for o in gen:
            queue.append(o)
        attrs['threads'] -= 1

    queue = deque[dict]()
    ths = [
        threading.Thread(
            target=thread_body,
            args=[
                queue,
                process(ids[o:-1:th]),
            ],
        )
        for o in range(0, th)
    ]

    def quit() -> None:
        attrs['quit'] = True
        for t in ths:
            t.join()

    for t in ths:
        t.start()

    try:
        while attrs['threads']:
            while len(queue) == 0:
                pass
            i, e = queue.pop()
            save.add_to_data(i, e)

            if e and grab.is_past_max(i, e):
                quit()
                return

    except KeyboardInterrupt:
        print('Quitting program soon...')
        quit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-incr", default=-1, required=False, type=int)
    parser.add_argument("-ss", default=-1, required=False, type=int)
    parser.add_argument("--stop", "-t", default=-1, required=False, type=int)
    parser.add_argument("--threads", default=13, required=False, type=int)
    args = parser.parse_args()

    if args.ss < 0:
        if args.incr > 0:
            args.ss = save.get_max()
        else:
            args.ss = save.get_min()

    if args.incr > 0 and args.stop < 0:
        args.stop = 88888888

    iterate(list(range(args.ss, args.stop, args.incr)), args.threads)
