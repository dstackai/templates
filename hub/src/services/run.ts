import { API } from 'api';
import { createApi } from '@reduxjs/toolkit/query/react';
import { fetchBaseQuery } from '@reduxjs/toolkit/query/react';

import fetchBaseQueryHeaders from 'libs/fetchBaseQueryHeaders';

import { RunsRequestParams } from './run.types';

export const runApi = createApi({
    reducerPath: 'runApi',
    baseQuery: fetchBaseQuery({
        prepareHeaders: fetchBaseQueryHeaders,
    }),

    tagTypes: ['Runs'],

    endpoints: (builder) => ({
        getRuns: builder.query<IRun[], RunsRequestParams>({
            query: ({ name, ...body }) => {
                return {
                    url: API.PROJECTS.RUNS_LIST(name),
                    method: 'POST',
                    body,
                };
            },

            providesTags: (result) =>
                result ? [...result.map(({ run_name }) => ({ type: 'Runs' as const, id: run_name })), 'Runs'] : ['Runs'],
        }),

        getRun: builder.query<IRun | undefined, RunsRequestParams>({
            query: ({ name, ...body }) => {
                return {
                    url: API.PROJECTS.RUNS_LIST(name),
                    method: 'POST',
                    body,
                };
            },

            transformResponse: (response: IRun[]) => response[0],

            providesTags: (result) => (result ? [{ type: 'Runs' as const, id: result?.run_name }] : []),
        }),
    }),
});

export const { useGetRunsQuery, useGetRunQuery } = runApi;
