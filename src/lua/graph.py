from __future__ import annotations
from collections.abc import Generator, Iterator
from itertools import repeat


class TreeNode:
    """represents node in a tree graph"""

    __slots__ = ()

    def descendants(self) -> Iterator[TreeNode]:
        """should return descendants in reversed order"""
        return iter(())

    def dfs(
        self,
    ) -> Generator[tuple[TreeNode, int, int, int], None, None]:
        """returns (node, depth, descendant number of node, number of node descendants)"""
        stack: list[tuple[tuple[int, TreeNode], int]] = [((0, self), 0)]
        while stack:
            (node_num, node), depth = stack.pop()
            d = len(stack)
            stack.extend(zip(enumerate(node.descendants()), repeat(depth + 1)))
            yield node, depth, node_num, len(stack) - d

    def get_log_string(self) -> Iterator[str]:
        """get log string representation of node line by line"""

        return iter(repr(self).split("\n"))

    def show(self) -> None:
        """simply shows tree for debug reasons"""

        first_syms: list[str] = []
        dfs_iter = self.dfs()

        # skip top node
        for s in next(dfs_iter)[0].get_log_string():
            print(s)

        for n, _, i, c in dfs_iter:
            str_iter = n.get_log_string()
            print(*first_syms, ("├" if i else "└"), "── ", next(str_iter), sep="")

            for s in str_iter:
                print(*first_syms, "    ", s, sep="")

            if i and c:
                first_syms.extend(("│", "    "))
            elif not i:
                first_syms.append("    ")

            if not (i or c):
                while first_syms and first_syms.pop() != "│":
                    pass
