from __future__ import annotations

from abc import ABCMeta
from abc import abstractmethod
from dataclasses import replace
from itertools import chain
from typing import Callable
from typing import Generic
from typing import Iterable
from typing import Mapping
from typing import Type
from typing import TypeVar

from rmshared.tools import as_is
from rmshared.tools import ensure_map_is_complete

from rmshared.content.taxonomy import core

from rmshared.content.taxonomy.variables import values
from rmshared.content.taxonomy.variables import arguments
from rmshared.content.taxonomy.variables import operators
from rmshared.content.taxonomy.variables.abc import Case
from rmshared.content.taxonomy.variables.abc import Scalar
from rmshared.content.taxonomy.variables.abc import IResolver

InCase = TypeVar('InCase')
OutCase = TypeVar('OutCase')
Operator = TypeVar('Operator', bound=operators.Operator)
Filter = TypeVar('Filter', bound=core.filters.Filter)
Label = TypeVar('Label', bound=core.labels.Label)
Range = TypeVar('Range', bound=core.ranges.Range)
Value = TypeVar('Value', bound=values.Value)


class Resolver(IResolver):
    def __init__(self):
        self.factory = self.Factory(self)

    def dereference_filters(self, operators_, arguments_):
        resolver = self.factory.make_filters_resolver(arguments_)
        return chain.from_iterable(map(resolver.dereference_operator, operators_))

    def dereference_filters_partially(self, operators_, arguments_):
        constant_filters = []
        variable_filters = []

        resolver = self.factory.make_filters_resolver(arguments_)
        for operator in operators_:
            try:
                constant_filters.extend(resolver.dereference_operator(operator))
            except IResolver.IArguments.ArgumentNotFoundException:
                variable_filters.append(operator)

        return constant_filters, variable_filters

    class Factory:
        def __init__(self, resolver: Resolver):
            self.resolver = resolver

        def make_filters_resolver(self, arguments_: Resolver.IArguments) -> Resolver.Operators[core.filters.Filter]:
            cases = self._make_filters_cases(arguments_)
            return self.resolver.Operators(cases, arguments_)

        def _make_labels_resolver(self, arguments_: Resolver.IArguments) -> Resolver.Operators[core.labels.Label]:
            cases = self._make_labels_cases(arguments_)
            return self.resolver.Operators(cases, arguments_)

        def _make_ranges_resolver(self, arguments_: Resolver.IArguments) -> Resolver.Operators[core.ranges.Range]:
            cases = self._make_ranges_cases(arguments_)
            return self.resolver.Operators(cases, arguments_)

        def _make_filters_cases(self, arguments_: Resolver.IArguments) -> Resolver.Filters:
            labels = self._make_labels_resolver(arguments_)
            ranges = self._make_ranges_resolver(arguments_)
            return self.resolver.Filters(labels, ranges)

        def _make_labels_cases(self, arguments_: Resolver.IArguments) -> Resolver.Labels:
            values_ = self._make_values_cases(arguments_)
            return self.resolver.Labels(values_)

        def _make_ranges_cases(self, arguments_: Resolver.IArguments) -> Resolver.Ranges:
            values_ = self._make_values_cases(arguments_)
            return self.resolver.Ranges(values_)

        def _make_values_cases(self, arguments_: Resolver.IArguments) -> Resolver.Values:
            return self.resolver.Values(arguments_)

    class Operators(Generic[Case]):
        def __init__(self, cases: ICases[Case, Case], arguments_: IResolver.IArguments):
            self.cases = cases
            self.arguments = arguments_
            self.operator_to_dereference_func_map: Mapping[Type[Operator], Callable[[Operator], Iterable[Case]]] = ensure_map_is_complete(operators.Operator, {
                operators.Switch: self._dereference_switch,
                operators.Return: self._dereference_return,
            })

        def dereference_operator(self, operator_: operators.Operator[Case]) -> Iterable[Case]:
            return self.operator_to_dereference_func_map[type(operator_)](operator_)

        def _dereference_switch(self, operator_: operators.Switch[Case]) -> Iterable[Case]:
            argument = self.arguments.get_argument(operator_.ref.alias)
            try:
                operator_ = operator_.cases[type(argument)]
            except LookupError:
                return iter([])
            else:
                return self.dereference_operator(operator_)

        def _dereference_return(self, operator_: operators.Return[Case]) -> Iterable[Case]:
            return map(self.cases.dereference_case, operator_.cases)

        class ICases(Generic[InCase, OutCase], metaclass=ABCMeta):
            @abstractmethod
            def dereference_case(self, case: InCase) -> OutCase:
                ...

    class Filters(Operators.ICases[core.filters.Filter, core.filters.Filter]):
        def __init__(self, labels: Resolver.Operators[core.filters.Label], ranges: Resolver.Operators[core.filters.Range]):
            self.labels = labels
            self.ranges = ranges
            self.filter_to_dereference_func_map: Mapping[Type[Filter], Callable[[Filter], Filter]] = ensure_map_is_complete(core.filters.Filter, {
                core.filters.AnyLabel: self._dereference_labels,
                core.filters.NoLabels: self._dereference_labels,
                core.filters.AnyRange: self._dereference_ranges,
                core.filters.NoRanges: self._dereference_ranges,
            })

        def dereference_case(self, case: core.filters.Filter) -> core.filters.Filter:
            return self.filter_to_dereference_func_map[type(case)](case)

        def _dereference_labels(self, case: Filter | core.filters.AnyLabel | core.filters.NoLabels) -> Filter:
            return replace(case, labels=tuple(chain.from_iterable(map(self.labels.dereference_operator, case.labels))))

        def _dereference_ranges(self, case: Filter | core.filters.AnyRange | core.filters.NoRanges) -> Filter:
            return replace(case, ranges=tuple(chain.from_iterable(map(self.ranges.dereference_operator, case.ranges))))

    class Labels(Operators.ICases[core.labels.Label, core.labels.Label]):
        def __init__(self, values_: Resolver.Operators.ICases[core.labels.Value, Scalar]):
            self.values = values_
            self.label_to_dereference_func_map: Mapping[Type[Label], Callable[[Label], Label]] = ensure_map_is_complete(core.labels.Label, {
                core.labels.Value: self._dereference_value,
                core.labels.Badge: as_is,
                core.labels.Empty: as_is,
            })

        def dereference_case(self, case: core.labels.Label) -> core.labels.Label:
            return self.label_to_dereference_func_map[type(case)](case)

        def _dereference_value(self, label: core.labels.Value) -> core.labels.Value:
            return replace(label, value=self.values.dereference_case(label.value))

    class Ranges(Operators.ICases[core.ranges.Range, core.ranges.Range]):
        def __init__(self, values_: Resolver.Operators.ICases[core.ranges.Value, Scalar]):
            self.values = values_
            self.range_to_dereference_func_map: Mapping[Type[Range], Callable[[Range], Range]] = ensure_map_is_complete(core.ranges.Range, {
                core.ranges.Between: self._dereference_between,
                core.ranges.LessThan: self._dereference_less_than,
                core.ranges.MoreThan: self._dereference_more_than,
            })

        def dereference_case(self, case: core.ranges.Range) -> core.ranges.Range:
            return self.range_to_dereference_func_map[type(case)](case)

        def _dereference_between(self, case: core.ranges.Between) -> core.ranges.Between:
            min_value = self.values.dereference_case(case.min_value)
            max_value = self.values.dereference_case(case.max_value)
            return replace(case, min_value=min_value, max_value=max_value)

        def _dereference_less_than(self, case: core.ranges.LessThan) -> core.ranges.LessThan:
            return replace(case, value=self.values.dereference_case(case.value))

        def _dereference_more_than(self, case: core.ranges.MoreThan) -> core.ranges.MoreThan:
            return replace(case, value=self.values.dereference_case(case.value))

    class Values(Operators.ICases[values.Value, Scalar]):
        def __init__(self, arguments_: Resolver.IArguments):
            self.arguments = arguments_
            self.value_to_dereference_func_map: Mapping[Type[Value], Callable[[Value], Value]] = ensure_map_is_complete(values.Value, {
                values.Variable: self._dereference_variable,
                values.Constant: self._dereference_constant,
            })

        def dereference_case(self, case: values.Value) -> Scalar:
            return self.value_to_dereference_func_map[type(case)](case)

        def _dereference_variable(self, case: values.Variable) -> Scalar:
            argument = self.arguments.get_argument(case.ref.alias)
            assert isinstance(argument, arguments.Value), [case, argument]
            return argument.values[case.index - 1]

        @staticmethod
        def _dereference_constant(case: values.Constant) -> Scalar:
            return case.value
