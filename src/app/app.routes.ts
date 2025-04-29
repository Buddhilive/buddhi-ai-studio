import { Routes } from '@angular/router';
import { DashboardComponent } from './pages/dashboard/dashboard.component';
import { SummarizationComponent } from './pages/summarization/summarization.component';

export const routes: Routes = [
    {
        path: '',
        component: DashboardComponent
    },
    {
        path: 'summarizer',
        component: SummarizationComponent,
        title: 'Summarization',
    },
    {
        path: '**',
        redirectTo: ''
    }
];
